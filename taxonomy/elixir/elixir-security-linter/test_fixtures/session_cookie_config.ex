# fixture: Endpoint session config missing http_only/secure + hardcoded salt
# Vulnerability: session cookie is readable by JS (XSS -> session theft),
# allows non-HTTPS transport, and signing_salt is hardcoded in source.
defmodule MyAppWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :my_app

  @session_options [
    store: :cookie,
    key: "_my_app_key",
    signing_salt: "dev-signing-salt-123",
    same_site: "None",
    max_age: 60 * 60 * 24 * 365 * 10
  ]

  plug Plug.Session, @session_options

  plug Plug.Static,
    at: "/",
    from: :my_app,
    gzip: false,
    only: ~w(assets fonts images favicon.ico robots.txt)

  plug MyAppWeb.Router
end
