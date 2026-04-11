# fixture: shared Team schema — referenced by belongs_to join challenges
defmodule MyApp.Accounts.Team do
  use Ecto.Schema
  import Ecto.Changeset

  schema "teams" do
    field :name, :string
    field :plan, :string, default: "free"

    has_many :users, MyApp.Accounts.User

    timestamps(type: :utc_datetime)
  end

  def changeset(team, attrs) do
    team
    |> cast(attrs, [:name, :plan])
    |> validate_required([:name])
  end
end
