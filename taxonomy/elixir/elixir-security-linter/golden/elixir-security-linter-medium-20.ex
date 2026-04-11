# golden: mass-assignment Map.put ordering bug fix — use split changesets
defmodule MyApp.Accounts.Profile do
  alias MyApp.Accounts.User
  import Ecto.Changeset

  def update_profile(%User{} = user, attrs) do
    user
    |> cast(attrs, [:email, :name])
    |> validate_required([:email])
  end
end
