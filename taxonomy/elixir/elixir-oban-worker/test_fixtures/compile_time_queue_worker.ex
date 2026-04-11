# fixture: a worker that calls Application.get_env/2 INSIDE `use Oban.Worker`
# `use` macros are evaluated at compile time, so the env lookup freezes at
# compile time — tests and prod end up sharing one queue unintentionally.
defmodule MyApp.Workers.ExportWorker do
  use Oban.Worker,
    queue: Application.get_env(:my_app, :export_queue, :default),
    max_attempts: Application.get_env(:my_app, :export_attempts, 3)

  alias MyApp.Exports

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"export_id" => id}}) do
    Exports.run(id)
  end
end
