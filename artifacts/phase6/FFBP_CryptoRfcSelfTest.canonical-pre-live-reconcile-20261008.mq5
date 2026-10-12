#property strict
#property script_show_inputs

#include <FFBP_Crypto.mqh>

bool ExpectHex(
   const string name,
   const string actual,
   const string expected
)
{
   if(StringCompare(StringToLower(actual),StringToLower(expected))==0)
   {
      Print("FFBP CRYPTO TEST PASS: ",name);
      return true;
   }

   Print("FFBP CRYPTO TEST FAIL: ",name);
   Print("  expected=",expected);
   Print("  actual  =",actual);
   return false;
}

bool ExpectBytes(
   const string name,
   const uchar &actual[],
   const string expected_hex
)
{
   return ExpectHex(
      name,
      FFBP_Hex(actual),
      expected_hex
   );
}

bool TestSHA256()
{
   // SHA-256("abc")
   uchar data[];
   StringToCharArray(
      "abc",
      data,
      0,
      StringLen("abc"),
      CP_UTF8
   );

   uchar digest[];

   if(!FFBP_SHA256(data,digest))
   {
      Print("FFBP CRYPTO TEST FAIL: SHA256 returned false");
      return false;
   }

   return ExpectBytes(
      "SHA256_abc",
      digest,
      "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD"
   );
}

bool TestHMAC()
{
   // RFC 4231 / standard HMAC-SHA256 test:
   //
   // key = "Jefe"
   // data = "what do ya want for nothing?"
   //
   // expected =
   // 5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843

   uchar key[];
   uchar message[];

   StringToCharArray(
      "Jefe",
      key,
      0,
      StringLen("Jefe"),
      CP_UTF8
   );

   StringToCharArray(
      "what do ya want for nothing?",
      message,
      0,
      StringLen("what do ya want for nothing?"),
      CP_UTF8
   );

   uchar digest[];

   if(!FFBP_HMAC_SHA256(key,message,digest))
   {
      Print("FFBP CRYPTO TEST FAIL: HMAC returned false");
      return false;
   }

   return ExpectBytes(
      "HMAC_SHA256_Jefe",
      digest,
      "5BDCC146BF60754E6A042426089575C75A003F089D2739839DEC58B964EC3843"
   );
}

bool TestHKDF()
{
   // RFC 5869 Appendix A.1
   //
   // Hash: SHA-256
   //
   // IKM:
   // 0b repeated 22 bytes
   //
   // salt:
   // 000102030405060708090a0b0c
   //
   // info:
   // f0f1f2f3f4f5f6f7f8f9
   //
   // L = 42
   //
   // Expected PRK:
   // 077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5
   //
   // Expected OKM:
   // 3cb25f25faacd57a90434f64d0362f2a
   // 2d2d0a90cf1a5a4c5db02d56ecc4c5bf
   // 34007208d5b887185865

   uchar ikm[];
   uchar salt[];
   uchar info[];

   if(!FFBP_HexDecode(
      "0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B0B",
      ikm
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: IKM decode");
      return false;
   }

   if(!FFBP_HexDecode(
      "000102030405060708090A0B0C",
      salt
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: salt decode");
      return false;
   }

   if(!FFBP_HexDecode(
      "F0F1F2F3F4F5F6F7F8F9",
      info
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: info decode");
      return false;
   }

   uchar prk[];

   if(!FFBP_HKDF_Extract(
      salt,
      ikm,
      prk
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: HKDF Extract returned false");
      return false;
   }

   bool prk_ok=ExpectBytes(
      "HKDF_Extract_RFC5869_A1",
      prk,
      "077709362C2E32DF0DDC3F0DC47BBA6390B6C73BB50F9C3122EC844AD7C2B3E5"
   );

   uchar okm[];

   if(!FFBP_HKDF_Expand(
      prk,
      info,
      42,
      okm
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: HKDF Expand returned false");
      return false;
   }

   bool okm_ok=ExpectBytes(
      "HKDF_Expand_RFC5869_A1",
      okm,
      "3CB25F25FAACD57A90434F64D0362F2A"
      "2D2D0A90CF1A5A4C5DB02D56ECC4C5BF"
      "34007208D5B887185865"
   );

   return prk_ok && okm_ok;
}

void OnStart()
{
   Print("==================================================");
   Print("FFBP CRYPTO RFC SELF-TEST");
   Print("==================================================");

   bool sha_ok=TestSHA256();
   bool hmac_ok=TestHMAC();
   bool hkdf_ok=TestHKDF();

   Print("==================================================");

   if(sha_ok && hmac_ok && hkdf_ok)
   {
      Print("FFBP CRYPTO SELF-TEST: GREEN");
      Print("SHA256=PASS");
      Print("HMAC-SHA256=PASS");
      Print("HKDF-SHA256=PASS");
   }
   else
   {
      Print("FFBP CRYPTO SELF-TEST: RED");
      Print("SHA256=",sha_ok ? "PASS" : "FAIL");
      Print("HMAC-SHA256=",hmac_ok ? "PASS" : "FAIL");
      Print("HKDF-SHA256=",hkdf_ok ? "PASS" : "FAIL");
   }

   Print("==================================================");
}
