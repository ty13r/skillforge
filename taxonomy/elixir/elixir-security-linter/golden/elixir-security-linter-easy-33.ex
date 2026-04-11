# golden: secrets-in-config fix — move to runtime.exs with System.fetch_env!/1
import Config

if config_env() == :prod do
  database_url =
    System.fetch_env!("DATABASE_URL")

  secret_key_base =
    System.fetch_env!("SECRET_KEY_BASE")

  config :my_app, MyApp.Repo,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10")

  config :my_app, MyAppWeb.Endpoint,
    secret_key_base: secret_key_base

  config :my_app, :stripe,
    publishable_key: System.fetch_env!("STRIPE_PUBLISHABLE_KEY"),
    secret_key: System.fetch_env!("STRIPE_SECRET_KEY")

  config :my_app, :sendgrid_api_key, System.fetch_env!("SENDGRID_API_KEY")
end
