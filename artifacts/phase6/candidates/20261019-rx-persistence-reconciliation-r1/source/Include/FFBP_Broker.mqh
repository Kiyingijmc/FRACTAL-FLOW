#ifndef __FFBP_BROKER_MQH__
#define __FFBP_BROKER_MQH__

#include <Trade/Trade.mqh>

// Broker adapter boundary. Strategy intent is not manufactured here.
CTrade g_ffbp_trade;

bool FFBP_IsSymbolTradeable(const string symbol)
{
   if(symbol=="") return false;
   long mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
   return mode!=SYMBOL_TRADE_MODE_DISABLED;
}

bool FFBP_NormalizeVolume(const string symbol,const double requested,double &volume)
{
   if(!MathIsValidNumber(requested) || requested<=0.0) return false;
   double vmin=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(vmin<=0.0 || vmax<=0.0 || step<=0.0) return false;
   if(requested<vmin || requested>vmax) return false;
   double q=MathFloor((requested-vmin)/step+1e-10);
   volume=vmin+q*step;
   return volume>=vmin-1e-12 && volume<=vmax+1e-12;
}

bool FFBP_ProtectivePosition(const ulong ticket,const double stop_loss,const double take_profit)
{
   // Fail closed: never submit a request that removes the protective stop.
   if(ticket==0 || !MathIsValidNumber(stop_loss) || !MathIsValidNumber(take_profit) ||
      stop_loss<=0.0 || take_profit<0.0)
      return false;

   if(!PositionSelectByTicket(ticket))
      return false;

   string symbol=PositionGetString(POSITION_SYMBOL);
   if(symbol=="")
      return false;

   double current_sl=PositionGetDouble(POSITION_SL);
   long type=PositionGetInteger(POSITION_TYPE);
   double bid=SymbolInfoDouble(symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(symbol,SYMBOL_ASK);
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || bid<=0.0 || ask<=0.0)
      return false;

   if(type==POSITION_TYPE_BUY)
   {
      if(stop_loss>=bid || (take_profit>0.0 && take_profit<=ask)) return false;
      if(current_sl>0.0 && stop_loss<current_sl) return false;
   }
   else if(type==POSITION_TYPE_SELL)
   {
      if(stop_loss<=ask || (take_profit>0.0 && take_profit>=bid)) return false;
      if(current_sl>0.0 && stop_loss>current_sl) return false;
   }
   else return false;

   ResetLastError();
   if(!g_ffbp_trade.PositionModify(ticket,stop_loss,take_profit))
      return false;

   // CTrade's bool is not broker-effect confirmation. Accept only explicit
   // server outcomes meaning applied or already unchanged.
   uint retcode=g_ffbp_trade.ResultRetcode();
   return (retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_NO_CHANGES);
}

#endif
