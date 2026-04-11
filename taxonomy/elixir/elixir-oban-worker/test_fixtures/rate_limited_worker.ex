# fixture: a worker that raises on a 429 rate-limit response
# The idiomatic Oban answer is to return {:snooze, retry_after} — raising
# burns an attempt and pollutes the error tracker with a non-bug.
defmodule MyApp.Workers.StripeSyncWorker do
  use Oban.Worker, queue: :external_api, max_attempts: 10

  alias MyApp.Stripe
  require Logger

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"customer_id" => customer_id}}) do
    case Stripe.sync_customer(customer_id) do
      {:ok, _customer} ->
        :ok

      {:error, %{status: 429, retry_after: retry_after}} ->
        Logger.warning("stripe rate limit hit, retrying in #{retry_after}s")
        raise "stripe rate limited, retry in #{retry_after}"

      {:error, reason} ->
        {:error, reason}
    end
  end
end
