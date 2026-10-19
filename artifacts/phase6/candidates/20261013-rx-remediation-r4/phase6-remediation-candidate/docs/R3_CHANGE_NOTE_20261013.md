# R3 change note — 2026-10-13

R3 adds one candidate-only hardening change relative to R2: OnInit rejects `InpMaxFrameBytes > 65536`, matching the FFBP/1 Python protocol maximum and preventing a user-configured uint from flowing into signed-int RX buffer arithmetic beyond the supported protocol limit. Two static regression tests cover the upper bound and ordering of validation before RX capacity arithmetic.

Evidence: 13 static tests passed; 21 full candidate tests passed. These tests do not compile or execute MQL5. The EA remains an unstamped candidate and is not reconciled with the exact Oct 12 canonical EA. No repository canonical file, deployed MT5 file, Git history, or live state was changed.


## R4 review note
R4 corrects the frame-limit ordering regression test, which in R3 compared offsets from different coordinate systems. See `R4_CHANGE_NOTE_20261013.md`. R3 is retained as historical candidate evidence and is not silently rewritten.
