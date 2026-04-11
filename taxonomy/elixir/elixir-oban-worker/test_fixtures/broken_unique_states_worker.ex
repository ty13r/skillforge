# fixture: unique config that excludes :available from :states
# Per Elixir Forum thread 69648, this configuration has crashed production
# queues by letting an incoming job collide with an already-available job.
# Parker Selbert (Oban maintainer) recommends :successful, :incomplete, or
# the full list — nothing else.
defmodule MyApp.Workers.ConversationUpdateWorker do
  use Oban.Worker,
    queue: :conversations,
    unique: [
      fields: [:queue, :worker, :args],
      keys: [:conversation_id],
      states: [:scheduled, :executing, :retryable],
      period: 60
    ]

  alias MyApp.Chat

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"conversation_id" => id}}) do
    Chat.recompute_summary(id)
    :ok
  end
end
