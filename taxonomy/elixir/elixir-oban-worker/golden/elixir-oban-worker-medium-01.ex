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
        Logger.info("stripe rate limit hit, snoozing #{retry_after}s")
        {:snooze, retry_after}

      {:error, %{status: 404}} ->
        {:cancel, :customer_not_found}

      {:error, reason} ->
        {:error, reason}
    end
  end
end
