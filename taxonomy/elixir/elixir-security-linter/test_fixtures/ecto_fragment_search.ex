# fixture: Ecto context doing SQL injection via fragment string interpolation
# Vulnerability: unsafe string interpolation in fragment/1 + Ecto.Adapters.SQL.query
# escape hatch. Fix uses ^ pin operator or parameterized queries.
defmodule MyApp.Catalog do
  import Ecto.Query, warn: false

  alias MyApp.Repo
  alias MyApp.Catalog.Product

  def search_products(term) do
    from(p in Product,
      where: fragment("name ILIKE '%#{term}%' OR description ILIKE '%#{term}%'")
    )
    |> Repo.all()
  end

  def products_created_after(date_str) do
    from(p in Product,
      where: fragment("inserted_at > '#{date_str}'::timestamp")
    )
    |> Repo.all()
  end

  def find_by_id(id) do
    sql = "SELECT * FROM products WHERE id = #{id}"
    {:ok, %{rows: rows}} = Ecto.Adapters.SQL.query(Repo, sql)
    rows
  end
end
