from typing import Dict
from langchain_openai import ChatOpenAI
from agents import firebase
from agents.state_models import CustomerInfo, FilteredMovers
from agents.config import Config
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate

from typing import List, Dict

# system prompt for creating a new negotiation strategy
planner_system_prompt = """You are a strategic negotiator. Based on the customer requirements and available movers,
you need to create a detailed negotiation instruction for a phone call that maximizes the customer's chances of getting the best price with good quality services.
 Be concise and write the plan in less than 10 sentences, and include key points only.
"""

class StrategistAgent:
    def __init__(self, user_id: str, model: str = Config.PLANNER_MODEL, database_path: str = "./agents/movers_database.csv"):
        self.llm = ChatOpenAI(model=model)
        self.user_id = user_id
        self.movers_db = pd.read_csv(database_path)

    def __call__(self, state: Dict) -> Dict:
        customer_info = state["customer_info"]
        # using the function below to select some movers from the list provided
        selected_movers = self._get_movers_data(customer_info)

        # add prompt and construct the chain
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", planner_system_prompt),
            ("human", f"Generate a concise instruction for guiding the voice agent to negotiate with the mover through a phone call. Make sure to include the customer information {customer_info}."),
        ])
        chain = self.prompt | self.llm
        response = chain.invoke({"customer_info": customer_info})

        firebase.update_data(self.user_id, {"strategy": response.content})

        print(f"Negotiation strategy: {response.content}")

        state["selected_movers"] = selected_movers
        state["negotiation_strategy"] = response
        state["customer_info"] = customer_info

        return state


    def _get_movers_data(self, customer_info: CustomerInfo) -> List[Dict]:
        """ Selecting relevant movers from the database of movers based on the customerinfo"""
        # Converting the database records into a list of dict
        movers = self.movers_db.to_dict('records')
        filter_prompt = ChatPromptTemplate.from_messages([
            ("system", """
                You are a helpful assistant that filters a list of mover vendors based on the user's criteria.
                First determine if the move is local or long distance based on the source and destination zipcodes,
                if zipcodes are not available try to assume them based on the greater area provided.
                Filter only the top 3 movers that best fit the user based on their information.
                Return the names of the filtered movers as a list.
                Also provide a rationale for the filtering.
            """),
            ("human", "Filter the list of movers: {movers} based on the customer information {customer_info}."),
        ])
        chain = filter_prompt | self.llm.with_structured_output(FilteredMovers)
        # Selecting some of the movers based on the customerinfo 
        response: FilteredMovers = chain.invoke({"customer_info": customer_info, "movers": movers})
        print("Filtered Movers: ", response)

        # filtering only the selected movers from the list of database movers records
        filtered_movers = [mover for mover in movers if mover["name"] in response.movers]
        # Updating this data in firebase
        firebase.update_data(self.user_id, {"movers": filtered_movers, "moverRationale": response.rationale})
        return filtered_movers