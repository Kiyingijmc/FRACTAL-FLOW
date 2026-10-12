#ifndef __FFBP_CRYPTO_MQH__
#define __FFBP_CRYPTO_MQH__

#include <FFBP_Json.mqh>

// FFBP/1 cryptographic primitives.
//
// MQL5 exposes SHA-256 through CryptEncode but not a native HMAC enum;
// HMAC-SHA256 is therefore constructed explicitly per RFC 2104/4231.
//
// IMPORTANT INTEROPERABILITY CONTRACT:
// The session context below MUST be byte-for-byte identical to the Python
// canonical JSON representation, which uses sort_keys=True.
//
// Canonical key order:
//   account_id
//   client_nonce
//   server_nonce
//   session_id
//   v
//
// Do not reorder these fields without simultaneously changing the Python
// canonical representation and all interoperability vectors.

string FFBP_Hex(const uchar &data[], const int count=-1)
{
   int n=count;
   if(n<0 || n>ArraySize(data))
      n=ArraySize(data);

   string out="";

   for(int i=0; i<n; i++)
      out+=StringFormat("%02X",data[i]);

   return out;
}

bool FFBP_HexDecode(const string hex, uchar &out[])
{
   int n=StringLen(hex);

   if((n&1)!=0)
      return false;

   ArrayResize(out,n/2);

   for(int i=0; i<n/2; i++)
   {
      string p=StringSubstr(hex,i*2,2);
      long v=StringToInteger("0x"+p);

      if(v<0 || v>255)
         return false;

      out[i]=(uchar)v;
   }

   return true;
}

bool FFBP_SHA256(const uchar &data[], uchar &digest[])
{
   uchar empty[];

   ArrayResize(empty,0);
   ArrayResize(digest,0);

   int n=CryptEncode(
      CRYPT_HASH_SHA256,
      data,
      empty,
      digest
   );

   return n==32;
}

void FFBP_XorBlock(
   const uchar &a[],
   const uchar &b[],
   uchar &out[]
)
{
   ArrayResize(out,64);

   for(int i=0; i<64; i++)
      out[i]=(uchar)(a[i]^b[i]);
}

bool FFBP_HMAC_SHA256(
   const uchar &key_in[],
   const uchar &message[],
   uchar &digest[]
)
{
   uchar key[];
   int key_len=ArraySize(key_in);

   // RFC 2104:
   // If K is longer than the hash block size, hash K first.
   if(key_len>64)
   {
      if(!FFBP_SHA256(key_in,key))
         return false;
   }
   else
   {
      ArrayResize(key,key_len);

      for(int i=0; i<key_len; i++)
         key[i]=key_in[i];
   }

   // Pad K to SHA-256 block size.
   ArrayResize(key,64);

   for(int i=key_len; i<64; i++)
      key[i]=0;

   uchar ipad[];
   uchar opad[];
   uchar inner[];
   uchar outer[];

   ArrayResize(ipad,64);
   ArrayResize(opad,64);

   for(int i=0; i<64; i++)
   {
      ipad[i]=(uchar)(key[i]^0x36);
      opad[i]=(uchar)(key[i]^0x5c);
   }

   // H((K xor ipad) || message)
   int inner_len=64+ArraySize(message);

   ArrayResize(inner,inner_len);

   ArrayCopy(
      inner,
      ipad,
      0,
      0,
      64
   );

   if(ArraySize(message)>0)
   {
      ArrayCopy(
         inner,
         message,
         64,
         0,
         ArraySize(message)
      );
   }

   uchar inner_hash[];

   if(!FFBP_SHA256(inner,inner_hash))
      return false;

   // H((K xor opad) || inner_hash)
   ArrayResize(outer,64+32);

   ArrayCopy(
      outer,
      opad,
      0,
      0,
      64
   );

   ArrayCopy(
      outer,
      inner_hash,
      64,
      0,
      32
   );

   return FFBP_SHA256(outer,digest);
}

bool FFBP_HMAC_Hex(
   const string secret,
   const uchar &message[],
   string &hex
)
{
   uchar key[];
   uchar digest[];

   StringToCharArray(
      secret,
      key,
      0,
      -1,
      CP_UTF8
   );

   int n=ArraySize(key);

   // Remove StringToCharArray's terminating NUL.
   if(n>0 && key[n-1]==0)
      ArrayResize(key,n-1);

   if(!FFBP_HMAC_SHA256(key,message,digest))
      return false;

   hex=FFBP_Hex(digest);

   return true;
}

bool FFBP_HMAC_HexBytes(
   const uchar &key_in[],
   const uchar &message[],
   string &hex
)
{
   uchar digest[];

   if(!FFBP_HMAC_SHA256(key_in,message,digest))
      return false;

   hex=FFBP_Hex(digest);

   return true;
}

// -----------------------------------------------------------------------------
// HKDF — RFC 5869
// -----------------------------------------------------------------------------

bool FFBP_HKDF_Extract(
   const uchar &salt[],
   const uchar &ikm[],
   uchar &prk[]
)
{
   return FFBP_HMAC_SHA256(
      salt,
      ikm,
      prk
   );
}

bool FFBP_HKDF_Expand(
   const uchar &prk[],
   const uchar &info[],
   const int length,
   uchar &okm[]
)
{
   if(length<0 || length>255*32)
      return false;

   ArrayResize(okm,length);

   if(length==0)
      return true;

   uchar previous[];

   ArrayResize(previous,0);

   int produced=0;

   for(int counter=1; produced<length; counter++)
   {
      int msg_len=
         ArraySize(previous)+
         ArraySize(info)+
         1;

      uchar msg[];

      ArrayResize(msg,msg_len);

      int off=0;

      if(ArraySize(previous)>0)
      {
         ArrayCopy(
            msg,
            previous,
            0,
            0,
            ArraySize(previous)
         );

         off+=ArraySize(previous);
      }

      if(ArraySize(info)>0)
      {
         ArrayCopy(
            msg,
            info,
            off,
            0,
            ArraySize(info)
         );

         off+=ArraySize(info);
      }

      msg[off]=(uchar)counter;

      uchar block[];

      if(!FFBP_HMAC_SHA256(
         prk,
         msg,
         block
      ))
      {
         return false;
      }

      int take=32;

      if(length-produced<take)
         take=length-produced;

      ArrayCopy(
         okm,
         block,
         produced,
         0,
         take
      );

      produced+=take;

      ArrayCopy(
         previous,
         block,
         0,
         0,
         32
      );
   }

   return true;
}

// -----------------------------------------------------------------------------
// FFBP/1 Session Key Derivation
// -----------------------------------------------------------------------------
//
// Canonical context MUST match Python:
//
// json.dumps(
//     {
//         "account_id": account_id,
//         "client_nonce": client_nonce_hex,
//         "server_nonce": server_nonce_hex,
//         "session_id": session_id,
//         "v": "FFBP/1",
//     },
//     sort_keys=True,
//     separators=(",", ":"),
// )
//
// Therefore the exact serialized byte order is:
//
// {"account_id":"...","client_nonce":"...",
//  "server_nonce":"...","session_id":"...","v":"FFBP/1"}
//
// There are deliberately NO spaces.
//
// c2s and s2c are each 32-byte HKDF outputs.
// -----------------------------------------------------------------------------

bool FFBP_DeriveSessionKeys(
   const string secret,
   const string account_id,
   const string session_id,
   const string client_nonce_hex,
   const string server_nonce_hex,
   uchar &c2s[],
   uchar &s2c[]
)
{
   if(
      StringLen(secret)==0 ||
      StringLen(client_nonce_hex)==0 ||
      StringLen(server_nonce_hex)==0
   )
   {
      return false;
   }

   // IMPORTANT:
   // This ordering is the lexicographically sorted Python representation:
   //
   // account_id
   // client_nonce
   // server_nonce
   // session_id
   // v
   //
   // This is the Phase 6 interoperability fix.
   string context=
      "{\"account_id\":\""+
      FFBP_JsonEscape(account_id)+
      "\",\"client_nonce\":\""+
      FFBP_JsonEscape(client_nonce_hex)+
      "\",\"server_nonce\":\""+
      FFBP_JsonEscape(server_nonce_hex)+
      "\",\"session_id\":\""+
      FFBP_JsonEscape(session_id)+
      "\",\"v\":\"FFBP/1\"}";

   // HKDF salt:
   //
   // SHA256(
   //   UTF-8(
   //     "FRACTAL-FLOW/FFBP/1/SALT" + context
   //   )
   // )
   string salt_text=
      "FRACTAL-FLOW/FFBP/1/SALT"+
      context;

   uchar salt_input[];

   StringToCharArray(
      salt_text,
      salt_input,
      0,
      -1,
      CP_UTF8
   );

   int n=ArraySize(salt_input);

   // Remove terminating NUL.
   if(n>0 && salt_input[n-1]==0)
      ArrayResize(salt_input,n-1);

   uchar salt[];

   if(!FFBP_SHA256(
      salt_input,
      salt
   ))
   {
      return false;
   }

   // IKM = UTF-8(shared secret)
   uchar secret_bytes[];

   StringToCharArray(
      secret,
      secret_bytes,
      0,
      -1,
      CP_UTF8
   );

   n=ArraySize(secret_bytes);

   // Remove terminating NUL.
   if(n>0 && secret_bytes[n-1]==0)
      ArrayResize(secret_bytes,n-1);

   uchar prk[];

   if(!FFBP_HKDF_Extract(
      salt,
      secret_bytes,
      prk
   ))
   {
      return false;
   }

   // Direction-specific HKDF info.
   //
   // c2s:
   // FRACTAL-FLOW/FFBP/1/c2s/<canonical-context>
   //
   // s2c:
   // FRACTAL-FLOW/FFBP/1/s2c/<canonical-context>

   string c2s_info_text=
      "FRACTAL-FLOW/FFBP/1/c2s/"+
      context;

   string s2c_info_text=
      "FRACTAL-FLOW/FFBP/1/s2c/"+
      context;

   uchar c2s_info[];
   uchar s2c_info[];

   StringToCharArray(
      c2s_info_text,
      c2s_info,
      0,
      -1,
      CP_UTF8
   );

   StringToCharArray(
      s2c_info_text,
      s2c_info,
      0,
      -1,
      CP_UTF8
   );

   n=ArraySize(c2s_info);

   // Remove terminating NUL.
   if(n>0 && c2s_info[n-1]==0)
      ArrayResize(c2s_info,n-1);

   n=ArraySize(s2c_info);

   // Remove terminating NUL.
   if(n>0 && s2c_info[n-1]==0)
      ArrayResize(s2c_info,n-1);

   if(!FFBP_HKDF_Expand(
      prk,
      c2s_info,
      32,
      c2s
   ))
   {
      return false;
   }

   if(!FFBP_HKDF_Expand(
      prk,
      s2c_info,
      32,
      s2c
   ))
   {
      return false;
   }

   return true;
}

#endif