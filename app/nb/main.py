# %%
%load_ext autoreload
%autoreload 2
#%%
from app.api import load_recipes,fetch_bazaar
#%%

recipes = load_recipes()
bazaar = fetch_bazaar()

# %%

bazaar[""]
# %%
