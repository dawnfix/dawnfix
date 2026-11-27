# hosted/

Only for Dawnfix Enterprise, the hosted part (status page, digest and alert emails, the Fleet
board). Everything else in this repo runs without it.

`service.sh` talks to the hosted service with your Enterprise key. Run it in your own
terminal, so the key never passes through a coding agent or a chat. The key comes from
`$DAWNFIX_LICENSE`, or the script asks for it without echo.

```sh
hosted/service.sh license                                  # what the key covers
hosted/service.sh workspace --emails a@example.com         # status page sign-in and digest recipients
hosted/service.sh client --name "Client Co" --emails it@client.example --repo owner/name
                                                           # a client workspace; its key goes straight
                                                           # into that repo's DAWNFIX_LICENSE secret
hosted/service.sh fleet-client --name "Client Co" [--emails ...] [--weekly on|off] [--auto-send on|off]
                                                           # a client on the Fleet board
```

`DAWNFIX_URL` overrides the service URL (default `https://dawnfix.dev`, https only). The
answers are JSON and never hold a key.

To get an Enterprise key, see https://dawnfix.dev/pricing.
