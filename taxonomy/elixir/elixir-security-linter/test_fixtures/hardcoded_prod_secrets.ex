# fixture: prod.exs with hardcoded secrets committed to source
# Vulnerability: API keys, DB passwords, and secret_key_base hardcoded as
# string literals in prod.exs. Sobelow Config.Secrets flags these.
import Config

config :my_app, MyAppWeb.Endpoint,
  url: [host: "example.com", port: 443],
  secret_key_base: "Zq8X4z3p9WnKvB2RLh6JmS0aY5Qd1xPvEuFgCkTjNqRsLh6JmS0aY5Qd1xPvEuFg",
  server: true

config :my_app, MyApp.Repo,
  username: "postgres",
  password: "super-secret-prod-password",
  hostname: "db.internal",
  database: "my_app_prod",
  pool_size: 15

config :my_app, :stripe,
  publishable_key: "pk_live_51Abc...",
  secret_key: "sk_live_51Abc...DeF"

config :my_app, :sendgrid_api_key, "SG.real_api_key_here.xxx"
