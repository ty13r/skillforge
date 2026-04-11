# fixture: Schema using the default timestamps() (naive_datetime) for a globally-distributed app
# Ecto maintainer quote: "I personally agree these would be the better defaults. But we can't
# change them without breaking existing apps." — Wojtek Mach, Ecto #2683
defmodule MyApp.Logging.LogEntry do
  use Ecto.Schema
  import Ecto.Changeset

  schema "log_entries" do
    field :message, :string
    field :level, :string
    field :source_system, :string

    # PROBLEM: default timestamps() uses :naive_datetime.
    # App serves users globally across time zones.
    timestamps()
  end

  def changeset(entry, attrs) do
    entry
    |> cast(attrs, [:message, :level, :source_system])
    |> validate_required([:message, :level])
  end
end
