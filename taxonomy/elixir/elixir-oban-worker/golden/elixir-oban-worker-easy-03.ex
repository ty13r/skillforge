defmodule MyApp.Workers.NotificationWorker do
  use Oban.Worker, queue: :notifications

  alias MyApp.Accounts
  alias MyApp.Notifications

  def enqueue(user, %DateTime{} = deliver_at) do
    %{
      "user_id" => user.id,
      "deliver_at" => DateTime.to_iso8601(deliver_at),
      "channel" => "push"
    }
    |> new()
    |> Oban.insert()
  end

  @impl Oban.Worker
  def perform(%Oban.Job{
        args: %{"user_id" => user_id, "deliver_at" => deliver_at_iso, "channel" => channel}
      }) do
    user = Accounts.get_user!(user_id)
    {:ok, deliver_at, _} = DateTime.from_iso8601(deliver_at_iso)
    Notifications.deliver(user, channel, deliver_at)
    :ok
  end
end
