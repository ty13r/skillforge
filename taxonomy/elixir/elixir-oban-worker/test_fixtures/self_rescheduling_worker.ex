# fixture: a worker that reschedules itself at the END of perform/1
# Per Sorentwo's "Reliable Scheduling" recipe, the reschedule must happen
# FIRST (before the business logic), otherwise retries re-trigger the
# reschedule and scheduled jobs grow exponentially.
defmodule MyApp.Workers.DigestWorker do
  use Oban.Worker, queue: :digests, max_attempts: 5

  alias MyApp.Digests

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"user_id" => user_id}}) do
    user = Digests.get_user_prefs!(user_id)
    Digests.build_and_send(user)

    %{"user_id" => user_id}
    |> new(schedule_in: 24 * 60 * 60)
    |> Oban.insert()

    :ok
  end
end
