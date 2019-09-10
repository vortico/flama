import React from 'react';
import { Admin, Resource, ListGuesser } from 'react-admin';
import jsonApiClient from 'ra-jsonapi-client';

const jsonApiSettings = {
  total: 'count',
  updateMethod: 'PUT',
};
const dataProvider = jsonApiClient('http://localhost:8000/', jsonApiSettings);


const App = () => (
  <Admin dataProvider={dataProvider}>
    <Resource name="puppy" list={ListGuesser} />
  </Admin>
);

export default App;
