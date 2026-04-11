import Config

config :my_app, Oban,
  repo: MyApp.Repo,
  queues: [default: 10, reports: 5, mailers: 20],
  plugins: [
    {Oban.Plugins.Pruner, max_age: 60 * 60 * 24 * 7},
    {Oban.Plugins.Cron,
     timezone: "America/New_York",
     crontab: [
       {"0 3 * * *", MyApp.Workers.NightlyCleanup},
       {"* * * * *", MyApp.Workers.HealthCheck},
       {"0 * * * *", MyApp.Workers.HourlyReport}
     ]}
  ]

config :my_app, :deps,
  notes: "Add `{:tz, \"~> 0.26\"}` to mix.exs deps and set Elixir's time zone database to Tz.TimeZoneDatabase in application.ex."
