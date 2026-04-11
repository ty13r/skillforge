# fixture: a worker using the DEPRECATED {:discard, reason} form
# Oban 2.17+ replaced :discard / {:discard, reason} with {:cancel, reason}.
# LLMs trained on pre-2024 blog posts still emit the deprecated form.
defmodule MyApp.Workers.WebhookDeliveryWorker do
  use Oban.Worker, queue: :webhooks, max_attempts: 8

  alias MyApp.Webhooks

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"webhook_id" => webhook_id}}) do
    case Webhooks.fetch(webhook_id) do
      {:ok, webhook} ->
        case Webhooks.deliver(webhook) do
          :ok -> :ok
          {:error, :permanent} -> {:discard, :permanent_failure}
          {:error, reason} -> {:error, reason}
        end

      {:error, :not_found} ->
        {:discard, :webhook_removed}
    end
  end
end
