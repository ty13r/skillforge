# fixture: Customer with a primary address — a canonical embeds_one candidate.
# The address is single-parent, never queried independently, and logically lives inside Customer.
defmodule MyApp.CRM.Customer do
  use Ecto.Schema
  import Ecto.Changeset

  schema "customers" do
    field :name, :string
    field :email, :string

    # TODO: primary_address — embed or associate?

    timestamps(type: :utc_datetime)
  end

  def changeset(customer, attrs) do
    customer
    |> cast(attrs, [:name, :email])
    |> validate_required([:name, :email])
  end
end
