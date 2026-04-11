defmodule MyApp.Workers.DailyReportWorker do
  use Oban.Worker,
    queue: :reports,
    max_attempts: 3,
    unique: [
      period: 86_400,
      keys: [:report_id, :date],
      states: [:available, :scheduled, :executing, :retryable]
    ]

  alias MyApp.Reports

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"report_id" => report_id, "date" => date}}) do
    Reports.generate_daily(report_id, Date.from_iso8601!(date))
  end
end
