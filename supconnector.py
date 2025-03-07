from supermarktconnector.ah import AHConnector

connector = AHConnector()
# connector.get_categories()
print(connector.get_product_details(4177))
