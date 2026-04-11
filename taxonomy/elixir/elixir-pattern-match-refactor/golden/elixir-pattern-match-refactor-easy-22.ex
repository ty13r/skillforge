defmodule MyApp.CommandParser do
  def parse(<<"SET ", rest::binary>>), do: {:set, rest}
  def parse(<<"GET ", rest::binary>>), do: {:get, rest}
  def parse(<<"DEL ", rest::binary>>), do: {:del, rest}
  def parse(<<"PING", rest::binary>>), do: {:ping, String.trim(rest)}
  def parse(_), do: {:error, :unknown}
end
