defmodule MyApp.Workers.ExportWorker do
  @moduledoc """
  Export worker.

  IMPORTANT: this worker uses STATIC `use Oban.Worker` options. Earlier
  versions called `Application.get_env/2` inside the `use` call — because
  `use` is a macro, those values were frozen at compile time, causing
  test and prod configuration to leak into the same worker definition.

  Per the Oban.Worker docs: 'Like all use macros, options are defined at
  compile time. Avoid using Application.get_env/2 to define worker
  options.' Any runtime overrides (e.g., per-environment queue names or
  attempt counts) live in the `enqueue/1` helper below, which reads
  Application config at runtime and passes them through `new/2`.
  """

  use Oban.Worker, queue: :exports, max_attempts: 3

  alias MyApp.Exports

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"export_id" => id}}) do
    Exports.run(id)
  end

  def enqueue(export_id) do
    queue = Application.get_env(:my_app, :export_queue, :exports)
    max_attempts = Application.get_env(:my_app, :export_attempts, 3)

    %{"export_id" => export_id}
    |> new(queue: queue, max_attempts: max_attempts)
    |> Oban.insert()
  end
end
