#property strict
#property script_show_inputs

#include <FFBP_Crypto.mqh>

// ============================================================================
// FFBP/1 CRYPTOGRAPHIC CONFORMANCE SELF-TEST
//
// Purpose:
//   Validate the exact production FFBP cryptographic primitives against
//   authoritative SHA-256, HMAC-SHA256 and RFC 5869 HKDF-SHA256 vectors.
//
// This script MUST NOT modify production cryptographic behaviour.
// It is a deterministic verification harness only.
//
// Expected production primitive chain:
//
//   SHA-256
//       |
//       +--> HMAC-SHA256
//                 |
//                 +--> HKDF-Extract
//                 |
//                 +--> HKDF-Expand
//
// ============================================================================


// ----------------------------------------------------------------------------
// Generic hexadecimal comparison
//
// FFBP_Hex() intentionally emits uppercase hexadecimal.
// Expected vectors are therefore also represented in uppercase.
//
// This avoids treating equivalent hexadecimal representations such as:
//
//   abcdef
//   ABCDEF
//
// as different byte sequences.
// ----------------------------------------------------------------------------

bool ExpectHex(
   const string name,
   const string actual,
   const string expected
)
{
   if(StringCompare(actual,expected)==0)
   {
      Print("FFBP CRYPTO TEST PASS: ",name);
      return true;
   }

   Print("FFBP CRYPTO TEST FAIL: ",name);
   Print("  expected=",expected);
   Print("  actual  =",actual);

   return false;
}


// ----------------------------------------------------------------------------
// Byte-array comparison helper
// ----------------------------------------------------------------------------

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


// ----------------------------------------------------------------------------
// Test 1: SHA-256
//
// SHA-256("abc")
//
// NIST/FIPS 180-4 well-known test vector.
// ----------------------------------------------------------------------------

bool TestSHA256()
{
   uchar data[];

   StringToCharArray(
      "abc",
      data,
      0,
      StringLen("abc"),
      CP_UTF8
   );

   uchar digest[];

   if(!FFBP_SHA256(
      data,
      digest
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: SHA256 returned false");
      return false;
   }

   return ExpectBytes(
      "SHA256_abc",
      digest,
      "BA7816BF8F01CFEA414140DE5DAE2223"
      "B00361A396177A9CB410FF61F20015AD"
   );
}


// ----------------------------------------------------------------------------
// Test 2: HMAC-SHA256
//
// RFC 4231 Test Case 2.
//
// Key:
//   "Jefe"
//
// Data:
//   "what do ya want for nothing?"
//
// Expected HMAC-SHA256:
//   5bdcc146bf60754e6a042426089575c7
//   5a003f089d2739839dec58b964ec3843
//
// RFC 4231 is the authoritative interoperability source for this vector.
// ----------------------------------------------------------------------------

bool TestHMAC()
{
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

   if(!FFBP_HMAC_SHA256(
      key,
      message,
      digest
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: HMAC returned false");
      return false;
   }

   return ExpectBytes(
      "HMAC_SHA256_Jefe",
      digest,
      "5BDCC146BF60754E6A042426089575C7"
      "5A003F089D2739839DEC58B964EC3843"
   );
}


// ----------------------------------------------------------------------------
// Test 3: Hexadecimal decoding
//
// This is a direct regression test for the production FFBP_HexDecode()
// primitive.
//
// Input:
//   00010203040506070809A0B0C0D0E0F
//
// Expected bytes:
//   00 01 02 03 04 05 06 07
//   08 09 0A 0B 0C 0D 0E 0F
//
// Both uppercase and lowercase forms should be accepted.
// ----------------------------------------------------------------------------

bool TestHexDecode()
{
   uchar decoded_upper[];
   uchar decoded_lower[];

   // 16 bytes:
   // 00 01 02 03 04 05 06 07
   // 08 09 0A 0B 0C 0D 0E 0F

   if(!FFBP_HexDecode(
      "000102030405060708090A0B0C0D0E0F",
      decoded_upper
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: HexDecode uppercase returned false");
      return false;
   }

   if(!ExpectBytes(
      "HexDecode_uppercase",
      decoded_upper,
      "000102030405060708090A0B0C0D0E0F"
   ))
   {
      return false;
   }

   if(!FFBP_HexDecode(
      "000102030405060708090a0b0c0d0e0f",
      decoded_lower
   ))
   {
      Print("FFBP CRYPTO TEST FAIL: HexDecode lowercase returned false");
      return false;
   }

   if(!ExpectBytes(
      "HexDecode_lowercase",
      decoded_lower,
      "000102030405060708090A0B0C0D0E0F"
   ))
   {
      return false;
   }

   return true;
}

// ----------------------------------------------------------------------------
// Test 4: RFC 5869 HKDF-SHA256 Appendix A.1
//
// Hash:
//   SHA-256
//
// IKM:
//   0b repeated 22 bytes
//
// Salt:
//   000102030405060708090a0b0c
//
// Info:
//   f0f1f2f3f4f5f6f7f8f9
//
// L:
//   42
//
// Expected PRK:
//
//   077709362c2e32df0ddc3f0dc47bba63
//   90b6c73bb50f9c3122ec844ad7c2b3e5
//
// Expected OKM:
//
//   3cb25f25faacd57a90434f64d0362f2a
//   2d2d0a90cf1a5a4c5db02d56ecc4c5bf
//   34007208d5b887185865
//
// RFC 5869 Appendix A.1.
// ----------------------------------------------------------------------------

bool TestHKDF()
{
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


   // -------------------------------------------------------------------------
   // HKDF-Extract
   // -------------------------------------------------------------------------

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
      "077709362C2E32DF0DDC3F0DC47BBA63"
      "90B6C73BB50F9C3122EC844AD7C2B3E5"
   );


   // -------------------------------------------------------------------------
   // HKDF-Expand
   // -------------------------------------------------------------------------

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


// ----------------------------------------------------------------------------
// Test runner
// ----------------------------------------------------------------------------

void OnStart()
{
   Print("==================================================");
   Print("FFBP CRYPTO RFC SELF-TEST");
   Print("==================================================");

   bool hex_ok=TestHexDecode();
   bool sha_ok=TestSHA256();
   bool hmac_ok=TestHMAC();
   bool hkdf_ok=TestHKDF();

   Print("==================================================");

   if(
      hex_ok &&
      sha_ok &&
      hmac_ok &&
      hkdf_ok
   )
   {
      Print("FFBP CRYPTO SELF-TEST: GREEN");
      Print("HexDecode=PASS");
      Print("SHA256=PASS");
      Print("HMAC-SHA256=PASS");
      Print("HKDF-SHA256=PASS");
   }
   else
   {
      Print("FFBP CRYPTO SELF-TEST: RED");
      Print("HexDecode=",hex_ok ? "PASS" : "FAIL");
      Print("SHA256=",sha_ok ? "PASS" : "FAIL");
      Print("HMAC-SHA256=",hmac_ok ? "PASS" : "FAIL");
      Print("HKDF-SHA256=",hkdf_ok ? "PASS" : "FAIL");
   }

   Print("==================================================");
}