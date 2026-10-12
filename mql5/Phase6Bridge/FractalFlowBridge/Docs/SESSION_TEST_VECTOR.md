# FFBP/1 Session Test Vector

Use this vector in `FFBP_SessionSelfTest.mq5` and independently in Python.

| Field | Value |
|---|---|
| secret | `shared-secret` |
| account_id | `ACC` |
| session_id | `SESSION` |
| client_nonce | 64 hex zeroes |
| server_nonce | 64 hex `11` bytes |
| c2s key | `8b231877fc4595fd47d0168a27851888fd4b053bee31be2f565eabe9810ba169` |
| s2c key | `0c0814372cb1bbe4bdde66f0ee484b718b2989c7a850f3c16812c2e78c954727` |
| proof | `abc0a20abca417cc9c5d02b44ec0540accb43d9cea8a434c6ebd7a595420b1ed` |

The vector is deterministic and contains no broker credentials.
