#property strict
#property script_show_inputs
#include "..\\Experts\\FractalFlowBridge\\Include\\FFBP_Crypto.mqh"

void OnStart()
{
   string message="The quick brown fox jumps over the lazy dog";
   string key="key";
   uchar m[],k[],d[];
   StringToCharArray(message,m,0,-1,CP_UTF8);
   StringToCharArray(key,k,0,-1,CP_UTF8);
   if(ArraySize(m)>0 && m[ArraySize(m)-1]==0) ArrayResize(m,ArraySize(m)-1);
   if(ArraySize(k)>0 && k[ArraySize(k)-1]==0) ArrayResize(k,ArraySize(k)-1);
   if(!FFBP_HMAC_SHA256(k,m,d)) { Print("FAIL: HMAC computation"); return; }
   string got=FFBP_Hex(d);
   StringToLower(got);
   string expected="f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8";
   if(got!=expected) Print("FAIL: expected ",expected," got ",got);
   else Print("PASS: RFC 4231-style HMAC test vector");
}
