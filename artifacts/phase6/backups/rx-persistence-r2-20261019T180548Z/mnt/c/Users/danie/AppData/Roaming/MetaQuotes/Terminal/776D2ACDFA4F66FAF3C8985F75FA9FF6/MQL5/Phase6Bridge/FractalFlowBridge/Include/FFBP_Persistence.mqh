#ifndef __FFBP_PERSISTENCE_MQH__
#define __FFBP_PERSISTENCE_MQH__

// Crash-safe candidate persistence for the EA command fence and safety state.
// FILE_COMMON is used so a terminal restart can recover the same lane state.
// Fields are length-prefixed; the persistence layer is local fencing/dedupe evidence,
// not broker truth. Full checksum/replay validation remains a later hardening gate.

#define FFBP_STATE_MAGIC 0x46464250
#define FFBP_STATE_VERSION 1

struct FFBP_CommandRecord
{
   string account_id;
   string command_id;
   string fingerprint;
   ulong session_epoch;
   string state;
   string broker_ref;
   string result;
};

string FFBP_StatePath(const string account_id,const string lane_id)
{
   return "FractalFlowBridge\\"+account_id+"\\"+lane_id+"\\state.bin";
}

bool FFBP_WriteString(int h,const string s)
{
   uchar b[];
   StringToCharArray(s,b,0,-1,CP_UTF8);
   int n=ArraySize(b);
   if(n>0 && b[n-1]==0) n--;
   FileWriteInteger(h,n,INT_VALUE);
   if(n>0) FileWriteArray(h,b,0,n);
   return true;
}

bool FFBP_ReadString(int h,string &s)
{
   if(FileIsEnding(h)) return false;
   int n=FileReadInteger(h,INT_VALUE);
   if(n<0 || n>1048576) return false;
   uchar b[];
   ArrayResize(b,n);
   if(n>0 && FileReadArray(h,b,0,n)!=n) return false;
   s=CharArrayToString(b,0,n,CP_UTF8);
   return true;
}

bool FFBP_SaveFence(const string account_id,const string lane_id,const ulong epoch)
{
   string tmp=FFBP_StatePath(account_id,lane_id)+".tmp";
   int h=FileOpen(tmp,FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(h==INVALID_HANDLE) return false;
   FileWriteInteger(h,FFBP_STATE_MAGIC,INT_VALUE);
   FileWriteInteger(h,FFBP_STATE_VERSION,INT_VALUE);
   FileWriteLong(h,(long)epoch);
   FileFlush(h);
   FileClose(h);
   string final_path=FFBP_StatePath(account_id,lane_id);
   // Replace through FileMove after deleting stale destination. Both operations
   // remain inside the MQL5 file sandbox; crash semantics are tested manually.
   return FileMove(tmp,FILE_COMMON,final_path,FILE_COMMON|FILE_REWRITE);
}

bool FFBP_LoadFence(const string account_id,const string lane_id,ulong &epoch)
{
   string path=FFBP_StatePath(account_id,lane_id);
   if(!FileIsExist(path,FILE_COMMON)) { epoch=0; return true; }
   int h=FileOpen(path,FILE_READ|FILE_BIN|FILE_COMMON|FILE_SHARE_READ);
   if(h==INVALID_HANDLE) return false;
   int magic=FileReadInteger(h,INT_VALUE);
   int ver=FileReadInteger(h,INT_VALUE);
   long e=FileReadLong(h);
   FileClose(h);
   if(magic!=FFBP_STATE_MAGIC || ver!=FFBP_STATE_VERSION || e<0) return false;
   epoch=(ulong)e;
   return true;
}

bool FFBP_AppendCommand(const string account_id,const string lane_id,const FFBP_CommandRecord &r)
{
   // Append-only evidence file. The EA must never treat this as broker truth;
   // it is local dedupe/fencing evidence only.
   string path="FractalFlowBridge\\"+account_id+"\\"+lane_id+"\\commands.log";
   int h=FileOpen(path,FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(h==INVALID_HANDLE) return false;
   FileSeek(h,0,SEEK_END);
   FileWriteInteger(h,0x434D4431,INT_VALUE);
   FileWriteInteger(h,1,INT_VALUE);
   FFBP_WriteString(h,r.account_id);
   FFBP_WriteString(h,r.command_id);
   FFBP_WriteString(h,r.fingerprint);
   FileWriteLong(h,(long)r.session_epoch);
   FFBP_WriteString(h,r.state);
   FFBP_WriteString(h,r.broker_ref);
   FFBP_WriteString(h,r.result);
   FileFlush(h);
   FileClose(h);
   return true;
}

#endif
