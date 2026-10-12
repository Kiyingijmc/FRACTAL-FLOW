#property strict
#property version   "1.1"
#property description "FRACTAL-FLOW FFBP/1 MT5 adapter — Phase 6 MQL5 candidate"

#include <FFBP_Crypto.mqh>
#include <FFBP_Json.mqh>
#include <FFBP_Persistence.mqh>
#include <FFBP_Broker.mqh>

input string InpBridgeHost="127.0.0.1";
input ushort InpBridgePort=39001;
input string InpAccountId="";
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
uchar g_rx_buffer[];

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
   if(StringLen(InpAccountId)==0 || StringLen(InpLaneId)==0) return false;
   if(StringLen(InpSharedSecret)==0) return false;
   if(!InpAllowReal && AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL) return false;
   return true;
}

bool ReadExact(uchar &out[],const int wanted,const uint timeout_ms)
{
   if(wanted<0 || wanted>(int)InpMaxFrameBytes+4) return false;
   ArrayResize(out,0);
   int received=0;
   ulong started=GetTickCount64();
   while(received<wanted)
   {
      if(GetTickCount64()-started>timeout_ms) return false;
      uint avail=SocketIsReadable(g_socket);
      if(avail==0) { Sleep(1); continue; }
      int want=wanted-received;
      if((uint)want>avail) want=(int)avail;
      uchar part[];
      int n=SocketRead(g_socket,part,(uint)want,0);
      if(n<=0) return false;
      int old=ArraySize(out);
      ArrayResize(out,old+n);
      ArrayCopy(out,part,old,0,n);
      received+=n;
   }
   return true;
}

uint ReadBE32(const uchar &b[],const int offset)
{
   return ((uint)b[offset]<<24)|((uint)b[offset+1]<<16)|((uint)b[offset+2]<<8)|(uint)b[offset+3];
}

void AppendBytes(uchar &dst[],const uchar &src[])
{
   int old=ArraySize(dst),n=ArraySize(src);
   ArrayResize(dst,old+n);
   if(n>0) ArrayCopy(dst,src,old,0,n);
}

bool ReadFrame(string &body)
{
   uchar prefix[];
   if(!ReadExact(prefix,4,25)) return false;
   uint len=ReadBE32(prefix,0);
   if(len==0 || len>InpMaxFrameBytes) return false;
   uchar data[];
   if(!ReadExact(data,(int)len,50)) return false;
   body=CharArrayToString(data,0,(int)len,CP_UTF8);
   return StringLen(body)>0;
}

bool VerifyEnvelope(const string body,string &type,string &account,string &session,
                    string &channel,ulong &seq,ulong &ack,string &cmd_id,string &correlation,
                    ulong &sent_at,ulong &deadline,bool &deadline_null,uint &flags,string &mac)
{
   string authenticated;
   if(!FFBP_RemoveMac(body,authenticated,mac)) return false;
   string expected;
   uchar msg[];
   StringToCharArray(authenticated,msg,0,-1,CP_UTF8);
   int n=ArraySize(msg); if(n>0 && msg[n-1]==0) ArrayResize(msg,n-1);
   if(!FFBP_HMAC_Hex(InpSharedSecret,msg,expected)) return false;
   string expected_lower=expected;
   string mac_lower=mac;
   StringToLower(expected_lower);
   StringToLower(mac_lower);
   if(StringCompare(expected_lower,mac_lower)!=0) return false;

   if(!FFBP_ParseStringValue(body,"type",type)) return false;
   if(!FFBP_ParseStringValue(body,"account_id",account)) return false;
   if(!FFBP_ParseStringValue(body,"session_id",session)) return false;
   if(!FFBP_ParseStringValue(body,"channel",channel)) return false;
   if(!FFBP_ParseUInt64(body,"seq",seq)) return false;
   if(!FFBP_ParseUInt64(body,"ack",ack)) return false;
   if(!FFBP_ParseUInt64(body,"sent_at_ms",sent_at)) return false;
   if(!FFBP_ParseUInt(body,"flags",flags)) return false;
   if(!FFBP_ParseStringValue(body,"cmd_id",cmd_id) && StringFind(body,"\"cmd_id\":null")<0) return false;
   if(!FFBP_ParseStringValue(body,"correlation_id",correlation) && StringFind(body,"\"correlation_id\":null")<0) return false;
   long d=0; if(!FFBP_ParseInt64OrNull(body,"deadline_ms",d,deadline_null)) return false;
   deadline=(ulong)(d<0?0:d);

   if(account!=InpAccountId || session!=g_session_id) return false;
   if(seq<=g_last_rx_seq) return false;
   return true;
}

bool SendBodyNoMac(const string body_no_mac)
{
   string mac;
   uchar msg[];
   StringToCharArray(body_no_mac,msg,0,-1,CP_UTF8);
   int n=ArraySize(msg); if(n>0 && msg[n-1]==0) ArrayResize(msg,n-1);
   if(!FFBP_HMAC_Hex(InpSharedSecret,msg,mac)) return false;
   // FFBP/1 canonical key order puts mac between flags and payload.
   int p=StringFind(body_no_mac,"\"payload\":");
   if(p<0) return false;
   string wire=StringSubstr(body_no_mac,0,p)+"\"mac\":\""+mac+"\","+StringSubstr(body_no_mac,p);
   uchar bytes[];
   StringToCharArray(wire,bytes,0,-1,CP_UTF8);
   n=ArraySize(bytes); if(n>0 && bytes[n-1]==0) ArrayResize(bytes,n-1);
   if(n>(int)InpMaxFrameBytes) return false;
   uchar frame[]; ArrayResize(frame,4+n);
   frame[0]=(uchar)((n>>24)&255); frame[1]=(uchar)((n>>16)&255); frame[2]=(uchar)((n>>8)&255); frame[3]=(uchar)(n&255);
   ArrayCopy(frame,bytes,4,0,n);
   int sent=SocketSend(g_socket,frame,ArraySize(frame));
   return sent==ArraySize(frame);
}

bool SendEnvelope(const string type,const string channel,const string cmd_id,const string correlation,
                  const string payload_json,const long deadline_ms=-1,const uint flags=0)
{
   string body;
   bool deadline_null=(deadline_ms<0);
   if(!FFBP_BuildEnvelopeNoMac(type,InpAccountId,g_session_id,channel,g_tx_seq,0,cmd_id,correlation,
                               (long)NowMs(),deadline_null,deadline_ms,flags,payload_json,body)) return false;
   if(!SendBodyNoMac(body)) return false;
   g_tx_seq++;
   return true;
}

bool SendHello()
{
   g_session_id=NewInstanceId();
   g_client_nonce=StringFormat("%I64u",GetTickCount64());
   string payload="{\"account_id\":\""+FFBP_JsonEscape(InpAccountId)+"\",\"client_nonce\":\""+
                  FFBP_JsonEscape(g_client_nonce)+"\",\"lane_id\":\""+FFBP_JsonEscape(InpLaneId)+
                  "\",\"terminal_login\":"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+
                  ",\"trade_mode\":"+IntegerToString((long)AccountInfoInteger(ACCOUNT_TRADE_MODE))+"}";
   return SendEnvelope("HELLO","CONTROL","","",payload);
}

bool HandleChallenge(const string body)
{
   string type,account,session,channel,cmd,correlation,mac;
   ulong seq,ack,sent,deadline; bool dn; uint flags;
   if(!VerifyEnvelope(body,type,account,session,channel,seq,ack,cmd,correlation,sent,deadline,dn,flags,mac)) return false;
   if(type!="CHALLENGE") return false;
   string payload;
   if(!FFBP_ExtractPayloadObject(body,payload)) return false;
   if(!FFBP_ParseStringValue(payload,"server_nonce",g_server_nonce)) return false;
   if(g_server_nonce=="") return false;

   // Phase 6 candidate: challenge is authenticated with the configured trust
   // secret. Session-derived key installation remains deliberately fail-closed
   // until the Python/MT5 handshake transcript is runtime-verified.
   g_protective_only=true;
   g_reconciliation_required=true;
   return false;
}

bool ProcessFrame(const string body)
{
   string type,account,session,channel,cmd,correlation,mac;
   ulong seq,ack,sent,deadline; bool dn; uint flags;
   if(!VerifyEnvelope(body,type,account,session,channel,seq,ack,cmd,correlation,sent,deadline,dn,flags,mac)) return false;
   g_last_rx_seq=seq;

   if(type=="HEARTBEAT") return SendEnvelope("ACK","CONTROL","",correlation,"{}",-1,0);
   if(type=="CHALLENGE") return HandleChallenge(body);
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
      return false;
   }
   return true;
}

bool ConnectBridge()
{
   if(g_socket!=INVALID_HANDLE) SocketClose(g_socket);
   g_socket=SocketCreate();
   if(g_socket==INVALID_HANDLE) return false;
   if(!SocketConnect(g_socket,InpBridgeHost,InpBridgePort,InpConnectTimeoutMs))
   {
      SocketClose(g_socket); g_socket=INVALID_HANDLE; return false;
   }
   return SendHello();
}

int OnInit()
{
   if(!ValidateIdentity()) return INIT_FAILED;
   if(InpTimerMs<10 || InpMaxFrameBytes<1024 || InpMaxDrainPerTimer==0) return INIT_FAILED;
   if(!FFBP_LoadFence(InpAccountId,InpLaneId,g_session_epoch)) return INIT_FAILED;
   g_session_epoch++;
   if(!FFBP_SaveFence(InpAccountId,InpLaneId,g_session_epoch)) return INIT_FAILED;
   g_protective_only=true;
   g_reconciliation_required=true;
   if(!ConnectBridge()) return INIT_FAILED;
   if(!EventSetMillisecondTimer((int)InpTimerMs)) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_socket!=INVALID_HANDLE) { SocketClose(g_socket); g_socket=INVALID_HANDLE; }
   g_authenticated=false;
   g_protective_only=true;
   g_reconciliation_required=true;
}

void OnTimer()
{
   if(g_socket==INVALID_HANDLE)
   {
      ConnectBridge();
      MaintainProtectiveState();
      return;
   }
   for(uint i=0;i<InpMaxDrainPerTimer;i++)
   {
      if(SocketIsReadable(g_socket)==0) break;
      string body;
      if(!ReadFrame(body) || !ProcessFrame(body))
      {
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
   if(!g_authenticated || g_reconciliation_required || g_quarantined)
      g_protective_only=true;
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   // O(1) evidence capture boundary. Never perform socket I/O or reconciliation here.
   // The full adapter will normalize this event into a bounded queue.
   // Parameters are intentionally observed only at the O(1) event boundary.
}
