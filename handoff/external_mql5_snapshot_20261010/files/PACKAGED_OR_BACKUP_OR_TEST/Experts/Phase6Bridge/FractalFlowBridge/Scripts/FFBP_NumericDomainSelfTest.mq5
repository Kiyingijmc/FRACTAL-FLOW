#property strict
#property script_show_inputs

#include "..\\Include\\FFBP_Json.mqh"

string ULongToDecimal(ulong value)
{
   if(value==0) return "0";
   string out="";
   while(value>0)
   {
      ulong digit=value%10;
      out=IntegerToString((long)digit)+out;
      value/=10;
   }
   return out;
}

bool CheckUInt64(const string label,const string decimal,const bool expect_ok,const string expect_value="")
{
   string json="{\"x\":"+decimal+"}";
   ulong value=0;
   bool ok=FFBP_ParseUInt64(json,"x",value);
   bool pass=(ok==expect_ok);
   if(pass && expect_ok && expect_value!="")
      pass=(ULongToDecimal(value)==expect_value);

   PrintFormat("G3-F UInt64 %-24s ok=%s value=%s expected_ok=%s expected_value=%s %s",
               label,ok?"true":"false",ULongToDecimal(value),
               expect_ok?"true":"false",expect_value,pass?"PASS":"FAIL");
   return pass;
}

bool CheckUInt32(const string label,const string decimal,const bool expect_ok)
{
   string json="{\"x\":"+decimal+"}";
   uint value=0;
   bool ok=FFBP_ParseUInt(json,"x",value);
   bool pass=(ok==expect_ok);
   PrintFormat("G3-F UInt32 %-24s ok=%s value=%u expected_ok=%s %s",
               label,ok?"true":"false",value,expect_ok?"true":"false",pass?"PASS":"FAIL");
   return pass;
}

bool CheckInt64(const string label,const string decimal,const bool expect_ok,const string expect_value="")
{
   string json="{\"x\":"+decimal+"}";
   long value=0;
   bool is_null=false;
   bool ok=FFBP_ParseInt64OrNull(json,"x",value,is_null);
   bool pass=(ok==expect_ok && !is_null);
   if(pass && expect_ok && expect_value!="")
      pass=(IntegerToString(value)==expect_value);

   PrintFormat("G3-F Int64  %-24s ok=%s value=%s null=%s expected_ok=%s expected_value=%s %s",
               label,ok?"true":"false",IntegerToString(value),is_null?"true":"false",
               expect_ok?"true":"false",expect_value,pass?"PASS":"FAIL");
   return pass;
}

bool CheckNull()
{
   string json="{\"x\":null}";
   long value=123;
   bool is_null=false;
   bool ok=FFBP_ParseInt64OrNull(json,"x",value,is_null);
   bool pass=(ok && is_null && value==0);
   PrintFormat("G3-F Int64  %-24s ok=%s value=%s null=%s %s",
               "null",ok?"true":"false",IntegerToString(value),is_null?"true":"false",pass?"PASS":"FAIL");
   return pass;
}

void OnStart()
{
   int total=0;
   int passed=0;

   // FFBP uint64 domain: [0, 2^64-1].
   total++; if(CheckUInt64("zero",       "0",                     true,  "0")) passed++;
   total++; if(CheckUInt64("one",        "1",                     true,  "1")) passed++;
   total++; if(CheckUInt64("uint32-max",  "4294967295",           true,  "4294967295")) passed++;
   total++; if(CheckUInt64("uint32-plus", "4294967296",           true,  "4294967296")) passed++;
   total++; if(CheckUInt64("int64-max",   "9223372036854775807",   true,  "9223372036854775807")) passed++;
   total++; if(CheckUInt64("int64-plus",  "9223372036854775808",   true,  "9223372036854775808")) passed++;
   total++; if(CheckUInt64("uint64-max",  "18446744073709551615",  true,  "18446744073709551615")) passed++;
   total++; if(CheckUInt64("uint64-over", "18446744073709551616",  false)) passed++;
   total++; if(CheckUInt64("negative",    "-1",                    false)) passed++;

   // FFBP uint32 domain used by flags.
   total++; if(CheckUInt32("uint32-zero",  "0",                    true)) passed++;
   total++; if(CheckUInt32("uint32-max",   "4294967295",           true)) passed++;
   total++; if(CheckUInt32("uint32-over",  "4294967296",           false)) passed++;

   // FFBP signed int64 parser domain.
   total++; if(CheckNull()) passed++;
   total++; if(CheckInt64("zero",          "0",                    true,  "0")) passed++;
   total++; if(CheckInt64("one",           "1",                    true,  "1")) passed++;
   total++; if(CheckInt64("int64-max",     "9223372036854775807",  true,  "9223372036854775807")) passed++;
   total++; if(CheckInt64("int64-over",    "9223372036854775808",  false)) passed++;
   total++; if(CheckInt64("minus-one",     "-1",                   true,  "-1")) passed++;
   total++; if(CheckInt64("int64-min",     "-9223372036854775808", true,  "-9223372036854775808")) passed++;
   total++; if(CheckInt64("int64-under",   "-9223372036854775809", false)) passed++;

   PrintFormat("G3-F_MQL5_NUMERIC_RESULT %d/%d",passed,total);
   if(passed==total)
      Print("G3-F_MQL5_NUMERIC_STATUS GREEN");
   else
      Print("G3-F_MQL5_NUMERIC_STATUS RED");
}
