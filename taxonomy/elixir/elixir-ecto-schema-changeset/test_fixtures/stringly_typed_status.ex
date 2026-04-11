# fixture: Schema using stringly-typed status with validate_inclusion.
# Better: use Ecto.Enum for compile-time enforcement.
defmodule MyApp.Tasks.Task do
  use Ecto.Schema
  import Ecto.Changeset

  schema "tasks" do
    field :title, :string
    field :status, :string
    field :priority, :string

    timestamps(type: :utc_datetime)
  end

  def changeset(task, attrs) do
    task
    |> cast(attrs, [:title, :status, :priority])
    |> validate_required([:title, :status])
    |> validate_inclusion(:status, ["pending", "in_progress", "done", "cancelled"])
    |> validate_inclusion(:priority, ["low", "medium", "high"])
  end
end
