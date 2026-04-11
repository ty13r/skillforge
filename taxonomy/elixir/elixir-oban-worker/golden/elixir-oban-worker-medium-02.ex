defmodule MyApp.Accounts do
  alias MyApp.Accounts.User
  alias MyApp.Repo
  alias MyApp.Workers.WelcomeEmailWorker

  def register_user(attrs) do
    changeset = User.registration_changeset(%User{}, attrs)

    Ecto.Multi.new()
    |> Ecto.Multi.insert(:user, changeset)
    |> Oban.insert(:welcome_email, fn %{user: user} ->
      WelcomeEmailWorker.new(%{"user_id" => user.id})
    end)
    |> Repo.transaction()
    |> case do
      {:ok, %{user: user}} -> {:ok, user}
      {:error, :user, changeset, _} -> {:error, changeset}
    end
  end
end
