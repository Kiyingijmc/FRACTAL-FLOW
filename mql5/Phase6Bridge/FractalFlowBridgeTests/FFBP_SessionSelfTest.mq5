#property strict
#property script_show_inputs
#include <FFBP_Crypto.mqh>

void OnStart()
{
   uchar c2s[],s2c[];
   if(!FFBP_DeriveSessionKeys("shared-secret","ACC","SESSION",
                              "0000000000000000000000000000000000000000000000000000000000000000",
                              "1111111111111111111111111111111111111111111111111111111111111111",
                              c2s,s2c))
   {
      Print("FAIL: HKDF derivation");
      return;
   }
   string c2s_hex=FFBP_Hex(c2s);
   string s2c_hex=FFBP_Hex(s2c);
   string expected_c2s="8B231877FC4595FD47D0168A27851888FD4B053BEE31BE2F565EABE9810BA169";
   string expected_s2c="0C0814372CB1BBE4BDDE66F0EE484B718B2989C7A850F3C16812C2E78C954727";
   if(c2s_hex!=expected_c2s || s2c_hex!=expected_s2c)
   {
      Print("FAIL: HKDF vector c2s=",c2s_hex," s2c=",s2c_hex);
      return;
   }
   string transcript="{\"account_id\":\"ACC\",\"client_nonce\":\"0000000000000000000000000000000000000000000000000000000000000000\",\"server_nonce\":\"1111111111111111111111111111111111111111111111111111111111111111\",\"session_id\":\"SESSION\",\"v\":\"FFBP/1\"}";
   uchar msg[];
   StringToCharArray(transcript,msg,0,-1,CP_UTF8);
   int n=ArraySize(msg); if(n>0 && msg[n-1]==0) ArrayResize(msg,n-1);
   string proof;
   if(!FFBP_HMAC_Hex("shared-secret",msg,proof))
   {
      Print("FAIL: proof");
      return;
   }
   if(proof!="abc0a20abca417cc9c5d02b44ec0540accb43d9cea8a434c6ebd7a595420b1ed")
   {
      Print("FAIL: proof vector got ",proof);
      return;
   }
   Print("PASS: FFBP session HKDF/proof vectors");
}
