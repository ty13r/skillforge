# fixture: a worker that shoves an Elixir struct directly into args
# Represents iron-law violation #3: structs serialize to a plain map and
# lose their __struct__ field, so matching on %User{} at perform-time crashes.
defmodule MyApp.Workers.NotificationWorker do
  use Oban.Worker, queue: :notifications

  alias MyApp.Accounts.User
  alias MyApp.Notifications

  def enqueue(%User{} = user, %DateTime{} = deliver_at) do
    %{user: user, deliver_at: deliver_at, channel: :push}
    |> new()
    |> Oban.insert()
  end

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"user" => %User{} = user, "deliver_at" => deliver_at}}) do
    Notifications.deliver_push(user, deliver_at)
    :ok
  end
end
