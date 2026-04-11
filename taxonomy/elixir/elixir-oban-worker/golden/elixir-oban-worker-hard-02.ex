defmodule MyApp.Workers.DigestWorker do
  use Oban.Worker, queue: :digests, max_attempts: 5

  alias MyApp.Digests

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"user_id" => user_id}, attempt: 1}) do
    %{"user_id" => user_id}
    |> new(schedule_in: 24 * 60 * 60)
    |> Oban.insert()

    user = Digests.get_user_prefs!(user_id)
    Digests.build_and_send(user)
    :ok
  end

  def perform(%Oban.Job{args: %{"user_id" => user_id}}) do
    user = Digests.get_user_prefs!(user_id)
    Digests.build_and_send(user)
    :ok
  end
end
