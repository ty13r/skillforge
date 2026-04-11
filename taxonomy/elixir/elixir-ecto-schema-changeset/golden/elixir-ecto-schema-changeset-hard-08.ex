# golden: soft delete with partial unique index + query scope helper
defmodule MyApp.Accounts.Member do
  use Ecto.Schema
  import Ecto.Changeset
  import Ecto.Query

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
    |> unique_constraint(:email, name: :members_email_active_index)
  end

  def active_query do
    from m in __MODULE__, where: is_nil(m.deleted_at)
  end

  def soft_delete_changeset(member) do
    change(member, deleted_at: DateTime.utc_now() |> DateTime.truncate(:second))
  end
end

defmodule MyApp.Repo.Migrations.AddPartialUniqueIndexMembers do
  use Ecto.Migration

  def change do
    create unique_index(:members, [:email],
             where: "deleted_at IS NULL",
             name: :members_email_active_index
           )
  end
end
