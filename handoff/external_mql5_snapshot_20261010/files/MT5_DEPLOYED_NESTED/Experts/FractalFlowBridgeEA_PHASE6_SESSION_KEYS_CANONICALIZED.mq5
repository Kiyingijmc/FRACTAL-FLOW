#property strict
#property version   "1.1"
#property description "FRACTAL-FLOW FFBP/1 MT5 adapter — Phase 6 MQL5 candidate"

#include <FFBP_Crypto.mqh>
#include <FFBP_Json.mqh>
#include <FFBP_Persistence.mqh>
#include <FFBP_Broker.mqh>

input string InpBridgeHost="127.0.0.1";
input ushort InpBridgePort=39001;
input string InpAccountId="104838909";
input string InpLaneId="";
input string InpSharedSecret="";
input bool   InpAllowReal=false;
input uint   InpTimerMs=50;
input uint   InpMaxFrameBytes=65536;
input uint   InpMaxDrainPerTimer=16;
input uint   InpConnectTimeoutMs=1000;

int g_socket=INVALID_HANDLE;
bool g_authenticated=false;
bool g_reconciliation_required=true;
bool g_protective_only=true;
bool g_quarantined=false;
ulong g_session_epoch=0;
ulong g_last_rx_seq=0;
ulong g_tx_seq=1;
string g_session_id="";
string g_server_nonce="";
string g_client_nonce="";
uchar g_session_key[];
uchar g_c2s_key[];
uchar g_s2c_key[];
uchar g_rx_buffer[];

// -----------------------------------------------------------------------------
// Time / identity
// -----------------------------------------------------------------------------

ulong NowMs()
{
   return GetTickCount64();
}

string NewInstanceId()
{
   // Instance identity is informational; durable fencing is the authority.
   return StringFormat("%I64u-%I64u",GetTickCount64(),ChartID());
}

bool ValidateIdentity()
{
   if(StringLen(InpAccountId)==0 || StringLen(InpLaneId)==0)
      return false;

   if(StringLen(InpSharedSecret)==0)
      return false;

   if(!InpAllowReal &&
      AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL)
      return false;

   return true;
}

// -----------------------------------------------------------------------------
// Framing / reads
// -----------------------------------------------------------------------------

bool ReadExact(uchar &out[],const int wanted,const uint timeout_ms)
{
   if(wanted<0 || wanted>(int)InpMaxFrameBytes+4)
      return false;

   ArrayResize(out,0);

   int received=0;
   ulong started=GetTickCount64();

   while(received<wanted)
   {
      if(GetTickCount64()-started>timeout_ms)
         return false;

      uint avail=SocketIsReadable(g_socket);

      if(avail==0)
      {
         Sleep(1);
         continue;
      }

      int want=wanted-received;

      if((uint)want>avail)
         want=(int)avail;

      uchar part[];

      int n=SocketRead(g_socket,part,(uint)want,0);

      if(n<=0)
         return false;

      int old=ArraySize(out);

      ArrayResize(out,old+n);
      ArrayCopy(out,part,old,0,n);

      received+=n;
   }

   return true;
}

uint ReadBE32(const uchar &b[],const int offset)
{
   return ((uint)b[offset]<<24)|
          ((uint)b[offset+1]<<16)|
          ((uint)b[offset+2]<<8)|
          (uint)b[offset+3];
}

void AppendBytes(uchar &dst[],const uchar &src[])
{
   int old=ArraySize(dst);
   int n=ArraySize(src);

   ArrayResize(dst,old+n);

   if(n>0)
      ArrayCopy(dst,src,old,0,n);
}

// Convert protocol text to exact UTF-8 bytes without a C-string terminator.
// FFBP/1 framing is length-delimited; 0x00 is never part of a JSON payload.
bool FFBP_StringToUtf8Exact(const string text,uchar &out[])
{
   ArrayResize(out,0);

   int source_chars=StringLen(text);

   if(source_chars==0)
      return true;

   int copied=StringToCharArray(
      text,
      out,
      0,
      source_chars,
      CP_UTF8);

   if(copied<=0)
      return false;

   // Protocol JSON emitted by this adapter is canonical escaped ASCII.
   if(copied!=source_chars)
      return false;

   if(ArraySize(out)!=source_chars)
      return false;

   if(out[ArraySize(out)-1]==0)
      return false;

   return true;
}

bool ReadFrame(string &body)
{
   uchar prefix[];

   if(!ReadExact(prefix,4,25))
      return false;

   uint len=ReadBE32(prefix,0);

   if(len==0 || len>InpMaxFrameBytes)
      return false;

   uchar data[];

   if(!ReadExact(data,(int)len,50))
      return false;

   body=CharArrayToString(data,0,(int)len,CP_UTF8);

   return StringLen(body)>0;
}

// -----------------------------------------------------------------------------
// Session transcript / proof
// -----------------------------------------------------------------------------

bool BuildSessionTranscript(string &transcript)
{
   // FFBP/1 canonical transcript: Python bytes.hex() is lowercase.
   // Normalize only the hexadecimal nonce fields participating in authentication.
   string client_nonce=g_client_nonce;
   string server_nonce=g_server_nonce;
   StringToLower(client_nonce);
   StringToLower(server_nonce);

   transcript="{\"account_id\":\""+FFBP_JsonEscape(InpAccountId)+
               "\",\"client_nonce\":\""+FFBP_JsonEscape(client_nonce)+
               "\",\"server_nonce\":\""+FFBP_JsonEscape(server_nonce)+
               "\",\"session_id\":\""+FFBP_JsonEscape(g_session_id)+
               "\",\"v\":\"FFBP/1\"}";
   return StringLen(transcript)>0;
}

bool ComputeSessionProof(string &proof)
{
   string transcript;

   if(!BuildSessionTranscript(transcript))
      return false;

   uchar msg[];

   if(!FFBP_StringToUtf8Exact(transcript,msg))
      return false;

   uchar transcript_hash[];

   if(!FFBP_SHA256(msg,transcript_hash))
   {
      Print("FFBP AUTH FAIL: transcript SHA256");
      return false;
   }

   PrintFormat(
      "FFBP AUTH DIAG: transcript=%s",
      transcript);

   PrintFormat(
      "FFBP AUTH DIAG: transcript_utf8_len=%d",
      ArraySize(msg));

   PrintFormat(
      "FFBP AUTH DIAG: transcript_sha256=%s",
      FFBP_Hex(transcript_hash));

   if(!FFBP_HMAC_Hex(InpSharedSecret,msg,proof))
   {
      Print("FFBP AUTH FAIL: HMAC-SHA256 proof");
      return false;
   }

   PrintFormat(
      "FFBP AUTH DIAG: proof=%s",
      proof);

   return true;
}

// -----------------------------------------------------------------------------
// Envelope verification
// -----------------------------------------------------------------------------

bool VerifyEnvelope(
   const string body,
   string &type,
   string &account,
   string &session,
   string &channel,
   ulong &seq,
   ulong &ack,
   string &cmd_id,
   string &correlation,
   ulong &sent_at,
   ulong &deadline,
   bool &deadline_null,
   uint &flags,
   string &mac)
{
   string authenticated;

   if(!FFBP_RemoveMac(body,authenticated,mac))
      return false;

   string expected;
   uchar msg[];

   if(!FFBP_StringToUtf8Exact(authenticated,msg))
      return false;

   int n=ArraySize(msg);

   if(g_authenticated)
   {
      if(!FFBP_HMAC_HexBytes(g_s2c_key,msg,expected))
         return false;
   }
   else
   {
      if(!FFBP_HMAC_Hex(InpSharedSecret,msg,expected))
         return false;
   }

   string expected_lower=expected;
   string mac_lower=mac;

   StringToLower(expected_lower);
   StringToLower(mac_lower);

   if(StringCompare(expected_lower,mac_lower)!=0)
      return false;

   if(!FFBP_ParseStringValue(body,"type",type))
      return false;

   if(!FFBP_ParseStringValue(body,"account_id",account))
      return false;

   if(!FFBP_ParseStringValue(body,"session_id",session))
      return false;

   if(!FFBP_ParseStringValue(body,"channel",channel))
      return false;

   if(!FFBP_ParseUInt64(body,"seq",seq))
      return false;

   if(!FFBP_ParseUInt64(body,"ack",ack))
      return false;

   if(!FFBP_ParseUInt64(body,"sent_at_ms",sent_at))
      return false;

   if(!FFBP_ParseUInt(body,"flags",flags))
      return false;

   if(!FFBP_ParseStringValue(body,"cmd_id",cmd_id) &&
      StringFind(body,"\"cmd_id\":null")<0)
      return false;

   if(!FFBP_ParseStringValue(body,"correlation_id",correlation) &&
      StringFind(body,"\"correlation_id\":null")<0)
      return false;

   long d=0;

   if(!FFBP_ParseInt64OrNull(body,"deadline_ms",d,deadline_null))
      return false;

   deadline=(ulong)(d<0 ? 0 : d);

   if(account!=InpAccountId || session!=g_session_id)
      return false;

   if(seq<=g_last_rx_seq)
      return false;

   return true;
}

// -----------------------------------------------------------------------------
// Envelope send
// -----------------------------------------------------------------------------

bool SendBodyNoMac(const string body_no_mac)
{
   string mac;
   uchar msg[];

   if(!FFBP_StringToUtf8Exact(body_no_mac,msg))
      return false;

   int n=ArraySize(msg);

   if(g_authenticated)
   {
      if(!FFBP_HMAC_HexBytes(g_c2s_key,msg,mac))
         return false;
   }
   else
   {
      if(!FFBP_HMAC_Hex(InpSharedSecret,msg,mac))
         return false;
   }

   int p=StringFind(body_no_mac,"\"payload\":");

   if(p<0)
      return false;

   string wire=
      StringSubstr(body_no_mac,0,p)+
      "\"mac\":\""+mac+"\","+
      StringSubstr(body_no_mac,p);

   uchar bytes[];

   if(!FFBP_StringToUtf8Exact(wire,bytes))
      return false;

   n=ArraySize(bytes);

   if(n>(int)InpMaxFrameBytes)
      return false;

   // Defense-in-depth: a C-string terminator is never legal in an FFBP
   // length-delimited JSON payload.
   if(n>0 && bytes[n-1]==0)
   {
      Print("FFBP SEND FAIL: protocol payload contains trailing NUL");
      return false;
   }

   uchar frame[];

   ArrayResize(frame,4+n);

   frame[0]=(uchar)((n>>24)&255);
   frame[1]=(uchar)((n>>16)&255);
   frame[2]=(uchar)((n>>8)&255);
   frame[3]=(uchar)(n&255);

   ArrayCopy(frame,bytes,4,0,n);

   int sent=SocketSend(g_socket,frame,ArraySize(frame));

   return sent==ArraySize(frame);
}

bool SendEnvelope(
   const string type,
   const string channel,
   const string cmd_id,
   const string correlation,
   const string payload_json,
   const long deadline_ms=-1,
   const uint flags=0)
{
   string body;

   bool deadline_null=(deadline_ms<0);

   if(!FFBP_BuildEnvelopeNoMac(
         type,
         InpAccountId,
         g_session_id,
         channel,
         g_tx_seq,
         0,
         cmd_id,
         correlation,
         (long)NowMs(),
         deadline_null,
         deadline_ms,
         flags,
         payload_json,
         body))
      return false;

   if(!SendBodyNoMac(body))
      return false;

   g_tx_seq++;

   return true;
}

// -----------------------------------------------------------------------------
// HELLO / authentication
// -----------------------------------------------------------------------------

bool SendHello()
{
   Print("FFBP HELLO: preparing HELLO");

   g_authenticated=false;
   g_quarantined=false;
   g_reconciliation_required=true;
   g_protective_only=true;

   g_last_rx_seq=0;
   g_tx_seq=1;

   ArrayResize(g_c2s_key,0);
   ArrayResize(g_s2c_key,0);

   g_session_id=NewInstanceId();

   PrintFormat("FFBP HELLO: session_id=%s",g_session_id);

   string entropy=
      StringFormat(
         "%I64u:%I64u:%I64u:%I64u",
         GetTickCount64(),
         ChartID(),
         (long)AccountInfoInteger(ACCOUNT_LOGIN),
         g_session_epoch);

   uchar entropy_bytes[];
   uchar entropy_hash[];

   if(!FFBP_StringToUtf8Exact(entropy,entropy_bytes))
   {
      Print("FFBP HELLO FAIL: UTF-8 serialization");
      return false;
   }

   int entropy_len=ArraySize(entropy_bytes);

   if(!FFBP_SHA256(entropy_bytes,entropy_hash))
   {
      Print("FFBP HELLO FAIL: SHA256");
      return false;
   }

   g_client_nonce=FFBP_Hex(entropy_hash);

   PrintFormat(
      "FFBP HELLO: client_nonce generated length=%d",
      StringLen(g_client_nonce));

   string payload=
      "{\"account_id\":\""+FFBP_JsonEscape(InpAccountId)+
      "\",\"client_nonce\":\""+
      FFBP_JsonEscape(g_client_nonce)+
      "\",\"lane_id\":\""+
      FFBP_JsonEscape(InpLaneId)+
      "\",\"terminal_login\":"+
      IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+
      ",\"trade_mode\":"+
      IntegerToString((long)AccountInfoInteger(ACCOUNT_TRADE_MODE))+
      "}";

   Print("FFBP HELLO: sending envelope");

   if(!SendEnvelope("HELLO","CONTROL","","",payload))
   {
      PrintFormat(
         "FFBP HELLO FAIL: SendEnvelope error=%d",
         GetLastError());

      return false;
   }

   Print("FFBP HELLO: sent");

   return true;
}

bool HandleChallenge(const string body)
{
   Print("FFBP SESSION: CHALLENGE received");

   // ProcessFrame() performs the authoritative envelope verification and
   // advances g_last_rx_seq before dispatch. Do not verify the same envelope
   // again here, because the replay guard would reject its already-consumed seq.
   string payload;

   if(!FFBP_ExtractPayloadObject(body,payload))
   {
      Print("FFBP SESSION FAIL: unable to extract CHALLENGE payload");
      return false;
   }

   if(!FFBP_ParseStringValue(payload,"server_nonce",g_server_nonce))
   {
      Print("FFBP SESSION FAIL: server_nonce missing");
      return false;
   }

   if(g_server_nonce=="")
   {
      Print("FFBP SESSION FAIL: server_nonce empty");
      return false;
   }

   PrintFormat(
      "FFBP SESSION: server_nonce received len=%d",
      StringLen(g_server_nonce));

   PrintFormat(
      "FFBP SESSION DIAG: session_id=%s",
      g_session_id);

   PrintFormat(
      "FFBP SESSION DIAG: client_nonce=%s",
      g_client_nonce);

   PrintFormat(
      "FFBP SESSION DIAG: server_nonce=%s",
      g_server_nonce);

   string proof;

   if(!ComputeSessionProof(proof))
   {
      Print("FFBP SESSION FAIL: ComputeSessionProof");
      return false;
   }

   string auth_payload=
      "{\"proof\":\""+
      FFBP_JsonEscape(proof)+
      "\"}";

   Print("FFBP SESSION: sending AUTH");

   if(!SendEnvelope(
         "AUTH",
         "CONTROL",
         "",
         "",
         auth_payload))
   {
      PrintFormat(
         "FFBP SESSION FAIL: AUTH SendEnvelope error=%d",
         GetLastError());

      return false;
   }

   Print("FFBP SESSION: AUTH sent");

   return true;
}

// -----------------------------------------------------------------------------
// Incoming frame processing
// -----------------------------------------------------------------------------

bool ProcessFrame(const string body)
{
   string type,account,session,channel,cmd,correlation,mac;
   ulong seq,ack,sent,deadline;
   bool dn;
   uint flags;

   if(!VerifyEnvelope(
         body,
         type,
         account,
         session,
         channel,
         seq,
         ack,
         cmd,
         correlation,
         sent,
         deadline,
         dn,
         flags,
         mac))
   {
      Print("FFBP RX FAIL: envelope verification");
      return false;
   }

   g_last_rx_seq=seq;

   PrintFormat(
      "FFBP RX: type=%s seq=%I64u ack=%I64u",
      type,
      seq,
      ack);

   if(type=="HEARTBEAT")
      return SendEnvelope("ACK","CONTROL","",correlation,"{}",-1,0);

   if(type=="CHALLENGE")
   {
      // Envelope authentication/replay validation has already completed above.
      return HandleChallenge(body);
   }

   if(type=="SESSION_ESTABLISHED")
   {
      Print("FFBP SESSION: SESSION_ESTABLISHED received");

      if(g_authenticated)
      {
         Print("FFBP SESSION FAIL: already authenticated");
         return false;
      }

      string payload;

      if(!FFBP_ExtractPayloadObject(body,payload))
      {
         Print("FFBP SESSION FAIL: unable to extract session payload");
         return false;
      }

      string c2s_hex,s2c_hex;

      if(!FFBP_ParseStringValue(payload,"c2s_key",c2s_hex))
      {
         Print("FFBP SESSION FAIL: c2s_key missing");
         return false;
      }

      if(!FFBP_ParseStringValue(payload,"s2c_key",s2c_hex))
      {
         Print("FFBP SESSION FAIL: s2c_key missing");
         return false;
      }

      if(!FFBP_HexDecode(c2s_hex,g_c2s_key) ||
         !FFBP_HexDecode(s2c_hex,g_s2c_key))
      {
         Print("FFBP SESSION FAIL: key hex decode");
         return false;
      }

      if(ArraySize(g_c2s_key)!=32 ||
         ArraySize(g_s2c_key)!=32)
      {
         PrintFormat(
            "FFBP SESSION FAIL: invalid key lengths c2s=%d s2c=%d",
            ArraySize(g_c2s_key),
            ArraySize(g_s2c_key));

         return false;
      }

      uchar expected_c2s[],expected_s2c[];

      // FFBP/1 canonical session-key derivation uses lowercase hex nonces,
      // matching Python bytes.hex() and the AUTH transcript canonicalization.
      string client_nonce=g_client_nonce;
      string server_nonce=g_server_nonce;
      StringToLower(client_nonce);
      StringToLower(server_nonce);

      if(!FFBP_DeriveSessionKeys(
            InpSharedSecret,
            InpAccountId,
            g_session_id,
            client_nonce,
            server_nonce,
            expected_c2s,
            expected_s2c))
      {
         Print("FFBP SESSION FAIL: local session-key derivation");
         return false;
      }

      if(StringCompare(
            FFBP_Hex(g_c2s_key),
            FFBP_Hex(expected_c2s))!=0 ||
         StringCompare(
            FFBP_Hex(g_s2c_key),
            FFBP_Hex(expected_s2c))!=0)
      {
         Print("FFBP SESSION FAIL: derived session keys mismatch");
         return false;
      }

      g_authenticated=true;
      g_protective_only=true;
      g_reconciliation_required=true;

      Print("FFBP SESSION: authenticated session established");

      return true;
   }

   if(type=="RESYNC_REQUIRED" || type=="SNAPSHOT")
   {
      g_reconciliation_required=true;
      g_protective_only=true;
      return true;
   }

   if(type=="ERROR")
   {
      g_protective_only=true;
      return true;
   }

   // Effectful COMMAND/RESULT processing is intentionally blocked until the
   // challenge/auth/session-key and durable command journal are fully wired.
   if(type=="COMMAND")
   {
      g_protective_only=true;
      g_reconciliation_required=true;

      Print("FFBP RX: COMMAND received while effectful path is locked");

      return false;
   }

   return true;
}

// -----------------------------------------------------------------------------
// Bridge connection
// -----------------------------------------------------------------------------

bool ConnectBridge()
{
   Print("FFBP CONNECT: entered");

   if(g_socket!=INVALID_HANDLE)
   {
      PrintFormat(
         "FFBP CONNECT: closing existing socket handle=%d",
         g_socket);

      SocketClose(g_socket);
      g_socket=INVALID_HANDLE;
   }

   Print("FFBP CONNECT: creating socket");

   g_socket=SocketCreate();

   if(g_socket==INVALID_HANDLE)
   {
      PrintFormat(
         "FFBP CONNECT FAIL: SocketCreate error=%d",
         GetLastError());

      return false;
   }

   PrintFormat(
      "FFBP CONNECT: socket created handle=%d",
      g_socket);

   PrintFormat(
      "FFBP CONNECT: connecting to %s:%u timeout=%u",
      InpBridgeHost,
      InpBridgePort,
      InpConnectTimeoutMs);

   ResetLastError();

   if(!SocketConnect(
         g_socket,
         InpBridgeHost,
         InpBridgePort,
         InpConnectTimeoutMs))
   {
      int error=GetLastError();

      PrintFormat(
         "FFBP CONNECT FAIL: SocketConnect error=%d",
         error);

      SocketClose(g_socket);
      g_socket=INVALID_HANDLE;

      return false;
   }

   Print("FFBP CONNECT: TCP connection established");

   Print("FFBP CONNECT: sending HELLO");

   ResetLastError();

   if(!SendHello())
   {
      int error=GetLastError();

      PrintFormat(
         "FFBP CONNECT FAIL: SendHello error=%d",
         error);

      return false;
   }

   Print("FFBP CONNECT: HELLO sent");

   return true;
}

// -----------------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------------

int OnInit()
{
   Print("==================================================");
   Print("FFBP INIT: entered");
   Print("==================================================");

   Print("FFBP INIT: validating identity");

   if(!ValidateIdentity())
   {
      Print("FFBP INIT FAIL: ValidateIdentity");

      return INIT_FAILED;
   }

   PrintFormat(
      "FFBP INIT: identity OK account=%s lane=%s allow_real=%s",
      InpAccountId,
      InpLaneId,
      InpAllowReal ? "true" : "false");

   PrintFormat(
      "FFBP INIT: TimerMs=%u MaxFrameBytes=%u MaxDrainPerTimer=%u ConnectTimeoutMs=%u",
      InpTimerMs,
      InpMaxFrameBytes,
      InpMaxDrainPerTimer,
      InpConnectTimeoutMs);

   if(InpTimerMs<10 ||
      InpMaxFrameBytes<1024 ||
      InpMaxDrainPerTimer==0)
   {
      Print("FFBP INIT FAIL: input validation");

      return INIT_FAILED;
   }

   Print("FFBP INIT: input validation OK");

   PrintFormat(
      "FFBP INIT: loading fence account=%s lane=%s",
      InpAccountId,
      InpLaneId);

   ResetLastError();

   if(!FFBP_LoadFence(
         InpAccountId,
         InpLaneId,
         g_session_epoch))
   {
      PrintFormat(
         "FFBP INIT FAIL: FFBP_LoadFence error=%d account=%s lane=%s",
         GetLastError(),
         InpAccountId,
         InpLaneId);

      return INIT_FAILED;
   }

   PrintFormat(
      "FFBP INIT: fence loaded epoch=%I64u",
      g_session_epoch);

   g_session_epoch++;

   PrintFormat(
      "FFBP INIT: saving fence epoch=%I64u",
      g_session_epoch);

   ResetLastError();

   if(!FFBP_SaveFence(
         InpAccountId,
         InpLaneId,
         g_session_epoch))
   {
      PrintFormat(
         "FFBP INIT FAIL: FFBP_SaveFence error=%d account=%s lane=%s epoch=%I64u",
         GetLastError(),
         InpAccountId,
         InpLaneId,
         g_session_epoch);

      return INIT_FAILED;
   }

   PrintFormat(
      "FFBP INIT: fence saved epoch=%I64u",
      g_session_epoch);

   g_protective_only=true;
   g_reconciliation_required=true;

   PrintFormat(
      "FFBP INIT: connecting bridge host=%s port=%u",
      InpBridgeHost,
      InpBridgePort);

   if(!ConnectBridge())
   {
      Print("FFBP INIT FAIL: ConnectBridge");

      return INIT_FAILED;
   }

   Print("FFBP INIT: bridge connected and HELLO sent");

   PrintFormat(
      "FFBP INIT: installing timer interval=%u ms",
      InpTimerMs);

   ResetLastError();

   if(!EventSetMillisecondTimer((int)InpTimerMs))
   {
      PrintFormat(
         "FFBP INIT FAIL: EventSetMillisecondTimer error=%d",
         GetLastError());

      return INIT_FAILED;
   }

   Print("FFBP INIT: SUCCESS");
   Print("==================================================");

   return INIT_SUCCEEDED;
}

// -----------------------------------------------------------------------------
// Deinitialization
// -----------------------------------------------------------------------------

void OnDeinit(const int reason)
{
   PrintFormat(
      "FFBP DEINIT: reason=%d",
      reason);

   EventKillTimer();

   if(g_socket!=INVALID_HANDLE)
   {
      SocketClose(g_socket);
      g_socket=INVALID_HANDLE;
   }

   g_authenticated=false;
   g_protective_only=true;
   g_reconciliation_required=true;

   ArrayResize(g_c2s_key,0);
   ArrayResize(g_s2c_key,0);
}

// -----------------------------------------------------------------------------
// Timer / runtime
// -----------------------------------------------------------------------------

void OnTimer()
{
   if(g_socket==INVALID_HANDLE)
   {
      Print("FFBP TIMER: socket unavailable; attempting reconnect");

      ConnectBridge();

      MaintainProtectiveState();

      return;
   }

   for(uint i=0;i<InpMaxDrainPerTimer;i++)
   {
      if(SocketIsReadable(g_socket)==0)
         break;

      string body;

      if(!ReadFrame(body) || !ProcessFrame(body))
      {
         Print("FFBP TIMER: frame processing failure; entering quarantine");

         g_quarantined=true;
         g_authenticated=false;
         g_protective_only=true;
         g_reconciliation_required=true;

         break;
      }
   }

   MaintainProtectiveState();
}

void MaintainProtectiveState()
{
   if(!g_authenticated ||
      g_reconciliation_required ||
      g_quarantined)
   {
      g_protective_only=true;
   }
}

// -----------------------------------------------------------------------------
// Trade observation boundary
// -----------------------------------------------------------------------------

void OnTradeTransaction(
   const MqlTradeTransaction &trans,
   const MqlTradeRequest &request,
   const MqlTradeResult &result)
{
   // O(1) evidence capture boundary. Never perform socket I/O or reconciliation here.
   // The full adapter will normalize this event into a bounded queue.
   // Parameters are intentionally observed only at the O(1) event boundary.
}