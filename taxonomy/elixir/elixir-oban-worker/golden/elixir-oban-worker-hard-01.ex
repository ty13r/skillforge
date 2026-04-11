defmodule MyApp.Workers.ConversationUpdateWorker do
  @moduledoc """
  Worker for recomputing conversation summaries.

  The unique block uses the FULL safe :states list. Per Parker Selbert
  (Oban maintainer) on Elixir Forum thread 69648, partial state lists that
  omit `:available` are unsafe and have caused production queues to crash
  by spawning hundreds of producers. Selbert recommends `:successful`,
  `:incomplete`, or the full list below — nothing else is production-safe.
  """

  use Oban.Worker,
    queue: :conversations,
    unique: [
      fields: [:queue, :worker, :args],
      keys: [:conversation_id],
      period: 60,
      states: [:available, :scheduled, :executing, :retryable, :completed, :cancelled, :discarded]
    ]

  alias MyApp.Chat

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"conversation_id" => id}}) do
    Chat.recompute_summary(id)
    :ok
  end
end
