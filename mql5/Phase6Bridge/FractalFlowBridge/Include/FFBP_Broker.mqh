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
   if(!PositionSelectByTicket(ticket)) return false;
   double current_sl=PositionGetDouble(POSITION_SL);
   double current_tp=PositionGetDouble(POSITION_TP);
   long type=PositionGetInteger(POSITION_TYPE);

   // Autonomous protection can tighten but never loosen an existing stop.
   if(type==POSITION_TYPE_BUY && current_sl>0.0 && stop_loss<current_sl) return false;
   if(type==POSITION_TYPE_SELL && current_sl>0.0 && stop_loss>current_sl) return false;

   return g_ffbp_trade.PositionModify(ticket,stop_loss,take_profit);
}

#endif
