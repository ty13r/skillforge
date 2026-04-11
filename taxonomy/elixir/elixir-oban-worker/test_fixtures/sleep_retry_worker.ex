# fixture: a worker that hand-rolls a retry loop with Process.sleep
# Oban already retries with exponential backoff; reinventing a retry loop
# inside perform/1 blocks a worker slot and ignores the max_attempts knob.
defmodule MyApp.Workers.SyncWorker do
  use Oban.Worker, queue: :sync, max_attempts: 1

  alias MyApp.ExternalAPI

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"entity_id" => id}}) do
    do_sync(id, 0)
  end

  defp do_sync(_id, attempt) when attempt >= 5 do
    {:error, :max_attempts_exhausted}
  end

  defp do_sync(id, attempt) do
    case ExternalAPI.sync(id) do
      {:ok, _} ->
        :ok

      {:error, :timeout} ->
        Process.sleep(1_000 * (attempt + 1))
        do_sync(id, attempt + 1)

      {:error, reason} ->
        {:error, reason}
    end
  end
end
