defmodule MyApp.Workers.WelcomeEmailWorker do
  use Oban.Worker, queue: :mailers

  alias MyApp.Accounts
  alias MyApp.Mailer

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"user_id" => user_id, "template" => template}}) do
    user = Accounts.get_user!(user_id)
    Mailer.send_welcome(user, template)
    :ok
  end

  def enqueue(user, template) do
    %{"user_id" => user.id, "template" => template}
    |> new()
    |> Oban.insert()
  end
end
