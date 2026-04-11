# fixture: config.exs using System.get_env at compile time
# Vulnerability: System.get_env is evaluated at compile time when placed in
# config.exs — the value is baked into the release. Should be runtime.exs
# with System.fetch_env!/1.
import Config

config :my_app, :api_key, System.get_env("STRIPE_KEY")
config :my_app, MyApp.Repo, url: System.get_env("DATABASE_URL")
config :my_app, :webhook_secret, System.get_env("WEBHOOK_SECRET") || "default-dev-secret"
