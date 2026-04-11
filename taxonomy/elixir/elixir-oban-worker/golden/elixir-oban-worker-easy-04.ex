defmodule MyApp.Workers.WebhookDeliveryWorker do
  use Oban.Worker, queue: :webhooks, max_attempts: 8

  alias MyApp.Webhooks

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"webhook_id" => webhook_id}}) do
    case Webhooks.fetch(webhook_id) do
      {:ok, webhook} ->
        case Webhooks.deliver(webhook) do
          :ok -> :ok
          {:error, :permanent} -> {:cancel, :permanent_failure}
          {:error, reason} -> {:error, reason}
        end

      {:error, :not_found} ->
        {:cancel, :webhook_removed}
    end
  end
end
