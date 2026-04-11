# fixture: a worker that passes a Decimal through args
# Decimal has no native JSON representation; Jason may fall back in ways
# that lose precision. The idiomatic fix is Decimal.to_string/1 on the way
# in, Decimal.new/1 on the way out.
defmodule MyApp.Workers.LedgerWorker do
  use Oban.Worker, queue: :ledger

  alias MyApp.Ledger

  def enqueue(account_id, %Decimal{} = amount) do
    %{account_id: account_id, amount: amount, currency: "USD"}
    |> new()
    |> Oban.insert()
  end

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"account_id" => account_id, "amount" => %Decimal{} = amount}}) do
    Ledger.credit(account_id, amount)
  end
end
