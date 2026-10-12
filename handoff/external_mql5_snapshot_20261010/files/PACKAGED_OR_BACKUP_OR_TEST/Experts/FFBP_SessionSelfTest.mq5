#property strict
#property script_show_inputs

#include <FFBP_Crypto.mqh>

// -----------------------------------------------------------------------------
// FFBP/1 Session Interoperability Self-Test
//
// This test verifies:
//   1. HKDF-SHA256 session-key derivation.
//   2. Deterministic transcript HMAC proof.
//
// The expected vectors are canonical Python interoperability vectors.
//
// IMPORTANT:
// Hexadecimal is normalized to uppercase before comparison. This prevents
// textual hex case from becoming a false interoperability failure.
// The underlying cryptographic bytes remain unchanged.
// -----------------------------------------------------------------------------

void OnStart()
{
   // --------------------------------------------------------------------------
   // Test inputs
   // --------------------------------------------------------------------------

   string secret="shared-secret";
   string account_id="ACC";
   string session_id="SESSION";

   string client_nonce_hex=
      "0000000000000000000000000000000000000000000000000000000000000000";

   string server_nonce_hex=
      "1111111111111111111111111111111111111111111111111111111111111111";

   // --------------------------------------------------------------------------
   // HKDF derivation
   // --------------------------------------------------------------------------

   uchar c2s[];
   uchar s2c[];

   if(!FFBP_DeriveSessionKeys(
      secret,
      account_id,
      session_id,
      client_nonce_hex,
      server_nonce_hex,
      c2s,
      s2c
   ))
   {
      Print("FAIL: HKDF derivation");
      return;
   }

   string c2s_hex=FFBP_Hex(c2s);
   string s2c_hex=FFBP_Hex(s2c);

   // Normalize generated hexadecimal.
   StringToUpper(c2s_hex);
   StringToUpper(s2c_hex);

   // Canonical Python interoperability vectors.
   string expected_c2s=
      "8B231877FC4595FD47D0168A27851888FD4B053BEE31BE2F565EABE9810BA169";

   string expected_s2c=
      "0C0814372CB1BBE4BDDE66F0EE484B718B2989C7A850F3C16812C2E78C954727";

   // Normalize expected hexadecimal as well.
   StringToUpper(expected_c2s);
   StringToUpper(expected_s2c);

   // --------------------------------------------------------------------------
   // Diagnostic lengths
   // --------------------------------------------------------------------------

   if(
      StringLen(c2s_hex)!=64 ||
      StringLen(s2c_hex)!=64
   )
   {
      Print(
         "FAIL: HKDF vector length c2s_len=",
         StringLen(c2s_hex),
         " s2c_len=",
         StringLen(s2c_hex)
      );

      return;
   }

   // --------------------------------------------------------------------------
   // HKDF vector comparison
   // --------------------------------------------------------------------------

   if(c2s_hex!=expected_c2s)
   {
      Print(
         "FAIL: c2s HKDF vector"
      );

      Print(
         "  got=",
         c2s_hex
      );

      Print(
         "  expected=",
         expected_c2s
      );

      return;
   }

   if(s2c_hex!=expected_s2c)
   {
      Print(
         "FAIL: s2c HKDF vector"
      );

      Print(
         "  got=",
         s2c_hex
      );

      Print(
         "  expected=",
         expected_s2c
      );

      return;
   }

   Print(
      "PASS: HKDF vectors"
   );

   // --------------------------------------------------------------------------
   // Deterministic transcript proof vector
   // --------------------------------------------------------------------------

   //
   // This MUST use the same canonical key ordering as the Python
   // implementation:
   //
   // account_id
   // client_nonce
   // server_nonce
   // session_id
   // v
   //
   // No whitespace.
   //

   string transcript=
      "{\"account_id\":\"ACC\",\"client_nonce\":\"0000000000000000000000000000000000000000000000000000000000000000\",\"server_nonce\":\"1111111111111111111111111111111111111111111111111111111111111111\",\"session_id\":\"SESSION\",\"v\":\"FFBP/1\"}";

   uchar msg[];

   StringToCharArray(
      transcript,
      msg,
      0,
      -1,
      CP_UTF8
   );

   // Remove terminating NUL added by StringToCharArray().
   int n=ArraySize(msg);

   if(n>0 && msg[n-1]==0)
      ArrayResize(msg,n-1);

   string proof;

   if(!FFBP_HMAC_Hex(
      secret,
      msg,
      proof
   ))
   {
      Print("FAIL: proof computation");
      return;
   }

   StringToUpper(proof);

   string expected_proof=
      "ABC0A20ABCA417CC9C5D02B44EC0540ACCB43D9CEA8A434C6EBD7A595420B1ED";

   StringToUpper(expected_proof);

   // --------------------------------------------------------------------------
   // Proof comparison
   // --------------------------------------------------------------------------

   if(StringLen(proof)!=64)
   {
      Print(
         "FAIL: proof vector length got_len=",
         StringLen(proof)
      );

      Print(
         "  got=",
         proof
      );

      return;
   }

   if(proof!=expected_proof)
   {
      Print(
         "FAIL: proof vector"
      );

      Print(
         "  got=",
         proof
      );

      Print(
         "  expected=",
         expected_proof
      );

      return;
   }

   Print(
      "PASS: proof vector"
   );

   // --------------------------------------------------------------------------
   // Final result
   // --------------------------------------------------------------------------

   Print(
      "PASS: FFBP session HKDF/proof vectors"
   );
}