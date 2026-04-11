# fixture: soft-delete column added but queries don't filter it out.
# Dashbit: "[handling soft deletes at the application level is] error prone."
defmodule MyApp.Accounts.Member do
  use Ecto.Schema
  import Ecto.Changeset

  schema "members" do
    field :email, :string
    field :display_name, :string
    field :deleted_at, :utc_datetime

    timestamps(type: :utc_datetime)
  end

  def changeset(member, attrs) do
    member
    |> cast(attrs, [:email, :display_name])
    |> validate_required([:email, :display_name])
  end

  # PROBLEM: this query returns soft-deleted members.
  # Need a default scope or helper that excludes them.
  import Ecto.Query

  def all_query do
    from m in __MODULE__
  end
end
