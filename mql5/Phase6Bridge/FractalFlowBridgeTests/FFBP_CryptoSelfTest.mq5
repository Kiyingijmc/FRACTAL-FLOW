#property strict
#property script_show_inputs
#include "..\\Experts\\FractalFlowBridge\\Include\\FFBP_Crypto.mqh"

bool FFBP_RunHmacVector(
   const string label,
   const string key_text,
   const string message_text,
   const string expected
)
{
   uchar key[], message[], digest[];

   StringToCharArray(key_text,key,0,-1,CP_UTF8);
   StringToCharArray(message_text,message,0,-1,CP_UTF8);

   if(ArraySize(key)>0 && key[ArraySize(key)-1]==0)
      ArrayResize(key,ArraySize(key)-1);

   if(ArraySize(message)>0 && message[ArraySize(message)-1]==0)
      ArrayResize(message,ArraySize(message)-1);

   if(!FFBP_HMAC_SHA256(key,message,digest))
   {
      Print("FAIL: ",label," HMAC computation");
      return false;
   }

   string actual=FFBP_Hex(digest);
   StringToLower(actual);

   if(actual!=expected)
   {
      Print("FAIL: ",label," expected=",expected," actual=",actual);
      return false;
   }

   Print("PASS: ",label);
   return true;
}

void OnStart()
{
   bool all_pass=true;

   // Existing RFC-style test vector.
   if(!FFBP_RunHmacVector(
      "RFC 4231-style HMAC test vector",
      "key",
      "The quick brown fox jumps over the lazy dog",
      "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8"
   ))
      all_pass=false;

   // FFBP/1 vector: authenticate the exact canonical body without "mac".
   string ffbp_body=
      "{\"account_id\":\"ACT_TEST\",\"ack\":0,\"channel\":\"CONTROL\","
      "\"cmd_id\":null,\"correlation_id\":null,\"deadline_ms\":null,"
      "\"flags\":0,\"payload\":{\"client_nonce\":\"nonce-001\","
      "\"lane_id\":\"PRIMARY\"},\"sent_at_ms\":1700000000000,"
      "\"seq\":1,\"session_id\":\"sess-001\",\"type\":\"HELLO\","
      "\"v\":\"FFBP/1\"}";

   if(!FFBP_RunHmacVector(
      "FFBP/1 canonical-envelope interoperability vector",
      "test-secret",
      ffbp_body,
      "d626bf7a97c099637bb7a0c07b2c4aa913830b2a2ff32f5cbcf947c4aba198e6"
   ))
      all_pass=false;

   // RFC 2104 long-key handling: 100-byte key.
   string long_key="";
   for(int i=0;i<100;i++)
      long_key+="a";

   if(!FFBP_RunHmacVector(
      "HMAC long-key regression (100 bytes)",
      long_key,
      "The quick brown fox jumps over the lazy dog",
      "ee128dd7d40b70b8e0f75153d8541bd8fd9685cf8fbec61719ed8b542b81f07c"
   ))
      all_pass=false;

   if(all_pass)
      Print("PASS: ALL FFBP CRYPTO SELF-TESTS");
   else
      Print("FAIL: ONE OR MORE FFBP CRYPTO SELF-TESTS");
}
