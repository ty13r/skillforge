# fixture: an application config that tries to run cron in America/New_York
# without declaring the tz dependency. Oban will crash on boot because
# Calendar has no non-UTC TZ database in core Elixir.
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
       {"*/30 * * * * *", MyApp.Workers.HealthCheck},
       {"0 * * * *", MyApp.Workers.HourlyReport}
     ]}
  ]
