# fixture: a context module that inserts a user and enqueues a follow-up
# job as two separate calls. A crash between the two leaves a user with
# no welcome email. The idiomatic fix is a single Ecto.Multi transaction.
defmodule MyApp.Accounts do
  alias MyApp.Accounts.User
  alias MyApp.Repo
  alias MyApp.Workers.WelcomeEmailWorker

  def register_user(attrs) do
    changeset = User.registration_changeset(%User{}, attrs)

    case Repo.insert(changeset) do
      {:ok, user} ->
        %{"user_id" => user.id}
        |> WelcomeEmailWorker.new()
        |> Oban.insert()

        {:ok, user}

      {:error, changeset} ->
        {:error, changeset}
    end
  end
end
