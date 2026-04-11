defmodule MyApp.Application do
  use Application

  @impl true
  def start(_type, _args) do
    :telemetry.attach_many(
      "oban-metrics-handler",
      [
        [:oban, :job, :start],
        [:oban, :job, :stop],
        [:oban, :job, :exception]
      ],
      &MyApp.ObanHandler.handle_event/4,
      nil
    )

    children = [
      MyApp.Repo,
      {Oban, Application.fetch_env!(:my_app, Oban)}
    ]

    opts = [strategy: :one_for_one, name: MyApp.Supervisor]
    Supervisor.start_link(children, opts)
  end
end

defmodule MyApp.ObanHandler do
  require Logger

  def handle_event([:oban, :job, :start], _measurements, %{worker: worker}, _config) do
    Logger.debug("oban job starting: #{worker}")
  end

  def handle_event([:oban, :job, :stop], measurements, %{worker: worker}, _config) do
    Logger.debug("oban job done: #{worker} in #{measurements.duration}ns")
  end

  def handle_event([:oban, :job, :exception], _measurements, metadata, _config) do
    Logger.error(
      "oban job failed: #{metadata.worker} kind=#{metadata.kind} reason=#{inspect(metadata.reason)}"
    )
  end
end
