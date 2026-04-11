# golden: fix unique_constraint by adding a matching unique_index in migration
defmodule MyApp.Accounts.Signup do
  use Ecto.Schema
  import Ecto.Changeset

  schema "signups" do
    field :email, :string
    field :username, :string
    field :referral_code, :string

    timestamps(type: :utc_datetime)
  end

  def changeset(signup, attrs) do
    signup
    |> cast(attrs, [:email, :username, :referral_code])
    |> validate_required([:email, :username])
    |> validate_format(:email, ~r/^[^\s]+@[^\s]+$/)
    |> unsafe_validate_unique(:email, MyApp.Repo)
    |> unsafe_validate_unique(:username, MyApp.Repo)
    |> unique_constraint(:email)
    |> unique_constraint(:username)
  end
end

defmodule MyApp.Repo.Migrations.AddUniqueIndexesToSignups do
  use Ecto.Migration

  def change do
    create unique_index(:signups, [:email])
    create unique_index(:signups, [:username])
  end
end
