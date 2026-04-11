# fixture: a worker that attaches a telemetry handler inside perform/1
# Every job execution leaks a new handler. The correct pattern is to
# attach once from application.ex at boot time.
defmodule MyApp.Workers.ReportWorker do
  use Oban.Worker, queue: :reports, max_attempts: 3

  alias MyApp.Reports
  require Logger

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"report_id" => report_id}} = job) do
    :telemetry.attach(
      "oban-error-#{report_id}",
      [:oban, :worker, :exception],
      fn _event, measurements, metadata, _config ->
        Logger.error("oban failure: #{inspect(measurements)} #{inspect(metadata)}")
      end,
      nil
    )

    Reports.generate(report_id, job.attempt)
  end
end
