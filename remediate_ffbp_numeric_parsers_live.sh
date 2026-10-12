#!/usr/bin/env bash
set -euo pipefail

FILE="$HOME/projects/FractalFlow/mql5/Phase6Bridge/FractalFlowBridge/Include/FFBP_Json.mqh"

if [[ ! -f "$FILE" ]]; then
    echo "ERROR: source file not found:"
    echo "  $FILE"
    exit 1
fi

BACKUP="$FILE.pre_numeric_remediation_$(date +%Y%m%d_%H%M%S).bak"
cp -p "$FILE" "$BACKUP"

python3 - "$FILE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

old_uint = '''bool FFBP_ParseUInt64(const string json,const string key,ulong &value)
{
   int p;
   if(!FFBP_FindKey(json,key,p)) return false;
   int start=p;
   int n=StringLen(json);
   while(p<n)
   {
      ushort c=StringGetCharacter(json,p);
      if(c<'0'||c>'9') break;
      p++;
   }
   if(p==start) return false;
   string t=StringSubstr(json,start,p-start);
   long v=StringToInteger(t);
   if(v<0) return false;
   value=(ulong)v;
   return true;
}'''

new_uint = '''bool FFBP_ParseUInt64(const string json,const string key,ulong &value)
{
   int p;
   if(!FFBP_FindKey(json,key,p)) return false;

   int start=p;
   int n=StringLen(json);

   while(p<n)
   {
      ushort c=StringGetCharacter(json,p);
      if(c<'0'||c>'9') break;
      p++;
   }

   if(p==start) return false;

   // Build the full unsigned 64-bit value digit by digit.
   // UINT64_MAX = 18446744073709551615.
   //
   // The final 20-digit boundary is checked lexicographically so
   // no overflowing integer literal is required.
   int digits=p-start;

   if(digits>20)
      return false;

   if(digits==20)
   {
      string max_uint64="18446744073709551615";
      string candidate=StringSubstr(json,start,20);

      if(StringCompare(candidate,max_uint64)>0)
         return false;
   }

   ulong acc=0;

   // For values within the proven decimal domain, multiplication
   // remains within ulong.
   for(int i=start;i<p;i++)
   {
      ulong digit=(ulong)(StringGetCharacter(json,i)-'0');
      acc=acc*10+digit;
   }

   value=acc;
   return true;
}'''

old_int = '''bool FFBP_ParseInt64OrNull(const string json,const string key,long &value,bool &is_null)
{
   int p;
   if(!FFBP_FindKey(json,key,p)) return false;
   if(StringSubstr(json,p,4)=="null") { is_null=true; value=0; return true; }
   is_null=false;
   bool neg=(StringGetCharacter(json,p)=='-');
   if(neg) p++;
   int start=p;
   while(p<StringLen(json))
   {
      ushort c=StringGetCharacter(json,p);
      if(c<'0'||c>'9') break;
      p++;
   }
   if(p==start) return false;
   long v=StringToInteger(StringSubstr(json,start,p-start));
   value=neg?-v:v;
   return true;
}'''

new_int = '''bool FFBP_ParseInt64OrNull(const string json,const string key,long &value,bool &is_null)
{
   int p;
   if(!FFBP_FindKey(json,key,p)) return false;

   if(StringSubstr(json,p,4)=="null")
   {
      is_null=true;
      value=0;
      return true;
   }

   is_null=false;

   bool neg=(StringGetCharacter(json,p)=='-');
   if(neg)
      p++;

   int start=p;
   int n=StringLen(json);

   while(p<n)
   {
      ushort c=StringGetCharacter(json,p);
      if(c<'0'||c>'9') break;
      p++;
   }

   if(p==start)
      return false;

   int digits=p-start;

   // INT64_MAX  =  9223372036854775807
   // INT64_MIN magnitude = 9223372036854775808
   string limit=neg
      ? "9223372036854775808"
      : "9223372036854775807";

   if(digits>19)
      return false;

   if(digits==19)
   {
      string candidate=StringSubstr(json,start,19);

      if(StringCompare(candidate,limit)>0)
         return false;
   }

   ulong magnitude=0;

   for(int i=start;i<p;i++)
   {
      ulong digit=(ulong)(StringGetCharacter(json,i)-'0');
      magnitude=magnitude*10+digit;
   }

   if(neg)
   {
      // INT64_MIN is represented without attempting to negate
      // its magnitude as a signed value.
      if(digits==19 &&
         StringSubstr(json,start,19)=="9223372036854775808")
      {
         value=(long)-9223372036854775807;
         value--;
      }
      else
      {
         value=-(long)magnitude;
      }
   }
   else
   {
      value=(long)magnitude;
   }

   return true;
}'''

if s.count(old_uint) != 1:
    raise SystemExit(
        f"ERROR: expected exactly one old UInt64 implementation, found {s.count(old_uint)}"
    )

if s.count(old_int) != 1:
    raise SystemExit(
        f"ERROR: expected exactly one old Int64 implementation, found {s.count(old_int)}"
    )

s=s.replace(old_uint,new_uint,1)
s=s.replace(old_int,new_int,1)

p.write_text(s,encoding="utf-8")
PY

echo
echo "PATCH_APPLIED"
echo "FILE: $FILE"
echo "BACKUP: $BACKUP"
echo
echo "CHECKING FOR OLD StringToInteger IMPLEMENTATIONS:"
if grep -n "StringToInteger" "$FILE"; then
    echo "ERROR: old numeric parser implementation remains."
    exit 1
else
    echo "OK: no StringToInteger references remain."
fi

echo
echo "SHA256:"
sha256sum "$FILE"

echo
echo "NEXT:"
echo "Compile FFBP_NumericDomainSelfTest.mq5 in MetaEditor."
echo "Require 0 errors, 0 warnings."
echo "Then require G3-F_MQL5_NUMERIC_RESULT 20/20."
