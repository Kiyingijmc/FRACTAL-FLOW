#property strict
#property version   "1.0"
#property description "FFBP native MT5 socket connectivity self-test; no protocol/authentication or broker effects"

input string InpHost="127.0.0.1";
input ushort InpPort=39001;
input uint   InpTimeoutMs=1000;

int OnInit()
{
   Print("FFBP SOCKET SELF TEST: starting");
   int socket=SocketCreate();
   if(socket==INVALID_HANDLE)
   {
      PrintFormat("FAIL: SocketCreate error=%d",GetLastError());
      return INIT_FAILED;
   }
   PrintFormat("PASS: SocketCreate handle=%d",socket);
   bool connected=SocketConnect(socket,InpHost,InpPort,InpTimeoutMs);
   if(!connected)
   {
      PrintFormat("FAIL: SocketConnect error=%d",GetLastError());
      SocketClose(socket);
      return INIT_FAILED;
   }
   Print("PASS: SocketConnect");
   SocketClose(socket);
   Print("PASS: socket closed");
   Print("FFBP SOCKET SELF TEST COMPLETE");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   PrintFormat("FFBP SOCKET SELF TEST DEINIT reason=%d",reason);
}
