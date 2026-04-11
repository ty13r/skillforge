# fixture: a daily-report worker with no unique constraint
# A human clicking "Generate report" twice enqueues two jobs. The fix is
# `unique: [period: 86_400, keys: [:report_id, :date]]` so only one copy
# of the same report runs per day.
defmodule MyApp.Workers.DailyReportWorker do
  use Oban.Worker, queue: :reports, max_attempts: 3

  alias MyApp.Reports

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"report_id" => report_id, "date" => date}}) do
    Reports.generate_daily(report_id, Date.from_iso8601!(date))
  end
end
