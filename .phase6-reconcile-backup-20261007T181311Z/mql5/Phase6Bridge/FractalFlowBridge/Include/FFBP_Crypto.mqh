#ifndef __FFBP_CRYPTO_MQH__
#define __FFBP_CRYPTO_MQH__

// FFBP/1 cryptographic primitives.
// MQL5 exposes SHA-256 through CryptEncode but not a native HMAC enum;
// HMAC-SHA256 is therefore constructed explicitly per RFC 2104/4231.

string FFBP_Hex(const uchar &data[], const int count=-1)
{
   int n=count;
   if(n<0 || n>ArraySize(data)) n=ArraySize(data);
   string out="";
   for(int i=0;i<n;i++) out+=StringFormat("%02X",data[i]);
   return out;
}

bool FFBP_HexDecode(const string hex, uchar &out[])
{
   int n=StringLen(hex);
   if((n&1)!=0) return false;
   ArrayResize(out,n/2);
   for(int i=0;i<n/2;i++)
   {
      string p=StringSubstr(hex,i*2,2);
      long v=StringToInteger("0x"+p);
      if(v<0 || v>255) return false;
      out[i]=(uchar)v;
   }
   return true;
}

bool FFBP_SHA256(const uchar &data[], uchar &digest[])
{
   uchar empty[];
   ArrayResize(empty,0);
   ArrayResize(digest,0);
   int n=CryptEncode(CRYPT_HASH_SHA256,data,empty,digest);
   return n==32;
}

void FFBP_XorBlock(const uchar &a[], const uchar &b[], uchar &out[])
{
   ArrayResize(out,64);
   for(int i=0;i<64;i++) out[i]=(uchar)(a[i]^b[i]);
}

bool FFBP_HMAC_SHA256(const uchar &key_in[], const uchar &message[], uchar &digest[])
{
   uchar key[];
   int key_len=ArraySize(key_in);
   if(key_len>64)
   {
      if(!FFBP_SHA256(key_in,key)) return false;
   }
   else
   {
      ArrayResize(key,key_len);
      for(int i=0;i<key_len;i++) key[i]=key_in[i];
   }
   ArrayResize(key,64);
   for(int i=key_len;i<64;i++) key[i]=0;

   uchar ipad[],opad[],inner[],outer[];
   ArrayResize(ipad,64); ArrayResize(opad,64);
   for(int i=0;i<64;i++) { ipad[i]=(uchar)(key[i]^0x36); opad[i]=(uchar)(key[i]^0x5c); }

   int inner_len=64+ArraySize(message);
   ArrayResize(inner,inner_len);
   ArrayCopy(inner,ipad,0,0,64);
   if(ArraySize(message)>0) ArrayCopy(inner,message,64,0,ArraySize(message));
   uchar inner_hash[];
   if(!FFBP_SHA256(inner,inner_hash)) return false;

   ArrayResize(outer,64+32);
   ArrayCopy(outer,opad,0,0,64);
   ArrayCopy(outer,inner_hash,64,0,32);
   return FFBP_SHA256(outer,digest);
}

bool FFBP_HMAC_Hex(const string secret, const uchar &message[], string &hex)
{
   uchar key[],digest[];
   StringToCharArray(secret,key,0,-1,CP_UTF8);
   int n=ArraySize(key);
   if(n>0 && key[n-1]==0) ArrayResize(key,n-1);
   if(!FFBP_HMAC_SHA256(key,message,digest)) return false;
   hex=FFBP_Hex(digest);
   return true;
}

#endif
