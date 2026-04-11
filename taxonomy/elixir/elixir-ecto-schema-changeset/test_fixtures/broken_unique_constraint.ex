# fixture: unique_constraint in changeset with NO matching unique_index in migration.
# Arrowsmith Labs: "unique_constraint/3 only achieves anything if your database
# actually has a uniqueness constraint on the given column."
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
    |> unique_constraint(:email)
    |> unique_constraint(:username)
  end
end

# And the (broken) migration the app was deployed with:
defmodule MyApp.Repo.Migrations.CreateSignups do
  use Ecto.Migration

  def change do
    create table(:signups) do
      add :email, :string, null: false
      add :username, :string, null: false
      add :referral_code, :string

      timestamps(type: :utc_datetime)
    end

    # NOTE: no unique_index on email or username.
    # The changeset unique_constraint does nothing.
  end
end
